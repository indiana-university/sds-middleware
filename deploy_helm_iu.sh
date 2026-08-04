#!/usr/bin/env sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
ENV_FILE="${ENV_FILE:-${SCRIPT_DIR}/.env}"
NAMESPACE="${NAMESPACE:-ua-vpit--research-technologies--rds}"
RELEASE_NAME="${RELEASE_NAME:-sds-middleware}"
HELM_TIMEOUT="${HELM_TIMEOUT:-10m}"
STATUS_INTERVAL="${STATUS_INTERVAL:-20}"
ROLLOUT_TOKEN="${ROLLOUT_TOKEN:-$(date -u '+%Y%m%d%H%M%S')}"
IMAGE_REGISTRY_SERVER="${IMAGE_REGISTRY_SERVER:-registry.docker.iu.edu}"
IMAGE_REPOSITORY="${IMAGE_REPOSITORY:-registry.docker.iu.edu/rds/sds-middleware}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
IMAGE_PULL_SECRET="${IMAGE_PULL_SECRET:-}"

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: env file not found at $ENV_FILE" >&2
  echo "Create it from .env.example and configure the remote database credentials." >&2
  exit 1
fi

if ! command -v kubectl >/dev/null || ! command -v helm >/dev/null; then
  echo "ERROR: kubectl and helm must both be installed." >&2
  exit 1
fi

read_optional_env() {
  sed -n "s/^$1=//p" "$ENV_FILE" | head -n 1
}

IMAGE_REGISTRY_USERNAME="${IMAGE_REGISTRY_USERNAME:-$(read_optional_env IMAGE_REGISTRY_USERNAME)}"
IMAGE_REGISTRY_PASSWORD="${IMAGE_REGISTRY_PASSWORD:-$(read_optional_env IMAGE_REGISTRY_PASSWORD)}"
IMAGE_REGISTRY_EMAIL="${IMAGE_REGISTRY_EMAIL:-$(read_optional_env IMAGE_REGISTRY_EMAIL)}"

if ! kubectl get namespace "$NAMESPACE" >/dev/null 2>&1; then
  echo "ERROR: namespace $NAMESPACE does not exist or is not accessible." >&2
  exit 1
fi

echo "Applying runtime configuration secret from $ENV_FILE..."
SECRET_OUT=$(kubectl create secret generic sds-middleware-env \
  --namespace "$NAMESPACE" \
  --from-env-file="$ENV_FILE" \
  2>&1) && echo "Runtime configuration secret created." || {
  if echo "$SECRET_OUT" | grep -q "already exists"; then
    echo "Runtime configuration secret already exists; reusing it."
  else
    echo "ERROR creating runtime configuration secret: $SECRET_OUT" >&2
    exit 1
  fi
}

USE_IMAGE_PULL_SECRET=false
if [ -n "$IMAGE_REGISTRY_USERNAME" ] && [ -n "$IMAGE_REGISTRY_PASSWORD" ]; then
  IMAGE_PULL_SECRET="${IMAGE_PULL_SECRET:-sds-middleware-registry}"
  echo "Applying image pull secret $IMAGE_PULL_SECRET..."
  REGISTRY_SECRET_OUT=$(kubectl create secret docker-registry "$IMAGE_PULL_SECRET" \
    --namespace "$NAMESPACE" \
    --docker-server="$IMAGE_REGISTRY_SERVER" \
    --docker-username="$IMAGE_REGISTRY_USERNAME" \
    --docker-password="$IMAGE_REGISTRY_PASSWORD" \
    --docker-email="${IMAGE_REGISTRY_EMAIL:-unused@example.com}" \
    2>&1) && echo "Image pull secret created." || {
    if echo "$REGISTRY_SECRET_OUT" | grep -q "already exists"; then
      echo "Image pull secret already exists; reusing it."
    else
      echo "ERROR creating image pull secret: $REGISTRY_SECRET_OUT" >&2
      exit 1
    fi
  }
  USE_IMAGE_PULL_SECRET=true
elif [ -n "$IMAGE_PULL_SECRET" ]; then
  USE_IMAGE_PULL_SECRET=true
fi

# This namespace may not permit reading Secrets. ConfigMap-backed Helm release
# metadata keeps application credentials out of Helm's storage.
export HELM_DRIVER=configmap
set -- \
  --set-string "namespace=${NAMESPACE}" \
  --set-string "sdsMiddleware.image.repository=${IMAGE_REPOSITORY}" \
  --set-string "sdsMiddleware.image.tag=${IMAGE_TAG}" \
  --set-string "sdsMiddleware.rolloutToken=${ROLLOUT_TOKEN}"

if [ "$USE_IMAGE_PULL_SECRET" = true ]; then
  set -- "$@" --set "sdsMiddleware.imagePullSecrets[0].name=${IMAGE_PULL_SECRET}"
fi

if [ -n "${INGRESS_HOST:-}" ]; then
  set -- "$@" --set ingress.enabled=true --set-string "ingress.host=${INGRESS_HOST}"
fi

echo "Deploying $RELEASE_NAME to $NAMESPACE with Helm release storage: $HELM_DRIVER"

print_deploy_status() {
  echo "" >&2
  echo "Waiting for Helm resources at $(date '+%Y-%m-%d %H:%M:%S')..." >&2
  kubectl get deployment,service -n "$NAMESPACE" -l "app.kubernetes.io/instance=${RELEASE_NAME}" 2>/dev/null || true
  kubectl get pods -n "$NAMESPACE" -l "app.kubernetes.io/instance=${RELEASE_NAME}" -o wide 2>/dev/null || true
  kubectl get events -n "$NAMESPACE" --sort-by=.lastTimestamp 2>/dev/null | tail -n 8 || true
}

watch_deploy_status() {
  while :; do
    sleep "$STATUS_INTERVAL"
    print_deploy_status
  done
}

stop_status_watcher() {
  if [ -n "${STATUS_PID:-}" ]; then
    kill "$STATUS_PID" 2>/dev/null || true
    wait "$STATUS_PID" 2>/dev/null || true
  fi
}

watch_deploy_status &
STATUS_PID=$!
trap stop_status_watcher EXIT INT TERM

if ! helm upgrade --install "$RELEASE_NAME" "${SCRIPT_DIR}/helm_iu" \
  --namespace "$NAMESPACE" \
  "$@" \
  --wait \
  --rollback-on-failure \
  --timeout "$HELM_TIMEOUT"; then
  stop_status_watcher
  echo "Helm deployment failed. Inspect namespace quota and recent events:" >&2
  echo "  kubectl describe resourcequota -n $NAMESPACE" >&2
  echo "  kubectl get events -n $NAMESPACE --sort-by=.lastTimestamp" >&2
  exit 1
fi

stop_status_watcher

echo "Deployment complete."
kubectl get deployment,service -n "$NAMESPACE" -l "app.kubernetes.io/instance=${RELEASE_NAME}"
