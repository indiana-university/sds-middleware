#!/usr/bin/env sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
ENV_FILE="${ENV_FILE:-${SCRIPT_DIR}/.env}"
NAMESPACE="${NAMESPACE:-ua-vpit--research-technologies--rds}"
RELEASE_NAME="${RELEASE_NAME:-sds-middleware}"
HELM_TIMEOUT="${HELM_TIMEOUT:-10m}"
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
kubectl create secret generic sds-middleware-env \
  --namespace "$NAMESPACE" \
  --from-env-file="$ENV_FILE" \
  --dry-run=client \
  --output=yaml | kubectl apply -f -

USE_IMAGE_PULL_SECRET=false
if [ -n "$IMAGE_REGISTRY_USERNAME" ] && [ -n "$IMAGE_REGISTRY_PASSWORD" ]; then
  IMAGE_PULL_SECRET="${IMAGE_PULL_SECRET:-sds-middleware-registry}"
  echo "Applying image pull secret $IMAGE_PULL_SECRET..."
  kubectl create secret docker-registry "$IMAGE_PULL_SECRET" \
    --namespace "$NAMESPACE" \
    --docker-server="$IMAGE_REGISTRY_SERVER" \
    --docker-username="$IMAGE_REGISTRY_USERNAME" \
    --docker-password="$IMAGE_REGISTRY_PASSWORD" \
    --docker-email="${IMAGE_REGISTRY_EMAIL:-unused@example.com}" \
    --dry-run=client \
    --output=yaml | kubectl apply -f -
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
helm upgrade --install "$RELEASE_NAME" "${SCRIPT_DIR}/helm_iu" \
  --namespace "$NAMESPACE" \
  "$@" \
  --wait \
  --rollback-on-failure \
  --timeout "$HELM_TIMEOUT"

echo "Deployment complete."
kubectl get deployment,service -n "$NAMESPACE" -l "app.kubernetes.io/instance=${RELEASE_NAME}"
