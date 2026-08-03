# Kubernetes deployment on OrbStack (macOS)

This deployment runs only SDS Middleware. It does not create a MySQL workload:
the application receives its remote database connection settings from a Kubernetes
Secret generated locally from `.env`.

## Prerequisites

1. Enable Kubernetes in OrbStack and select its context:

   ```bash
   kubectl config use-context orbstack
   kubectl get nodes
   ```

2. Build the image locally. OrbStack makes locally built Docker images available
   to its Kubernetes cluster.

   ```bash
   docker build -t sds-middleware:latest .
   ```

3. Create `.env` from the template and set the remote database values. The
   `DATABASE__HOST` must be reachable from the OrbStack Kubernetes VM.

   ```bash
   cp .env.example .env
   # Edit DATABASE__HOST, DATABASE__PORT, DATABASE__USER, DATABASE__PASSWORD, and DATABASE__DB.
   ```

`.env` is never committed or included in the image. The deployment script converts
it to the `sds-runtime-env` Kubernetes Secret in the `sds-middleware` namespace.

## Deploy

From the repository root:

```bash
./k8s/deploy.sh
```

The script targets the `orbstack` context by default. To use a differently named
OrbStack context, set `K8S_CONTEXT` when invoking it.

The script creates the namespace, applies the `.env` secret, deploys the app, and
waits for the pod to become Ready. Readiness calls `/config/db` from inside the
container, so it succeeds only when the remote database connection works.

## Verify

```bash
kubectl get pods,service -n sds-middleware
kubectl logs -n sds-middleware deployment/sds-middleware-app --tail=100
kubectl exec -n sds-middleware deployment/sds-middleware-app -- \
  sh -c 'curl --fail -H "X-Client-Secret: $WEBSERVER__CLIENT_SECRET" http://localhost:8080/config/db'
```

OrbStack exposes the LoadBalancer service at `http://localhost:8080`. The database
status endpoint requires the configured client secret.

## Update configuration

After changing `.env`, recreate the runtime secret and restart the deployment:

```bash
kubectl create secret generic sds-runtime-env --from-env-file=.env \
  --namespace=sds-middleware --dry-run=client --output=yaml | kubectl apply -f -
kubectl rollout restart deployment/sds-middleware-app -n sds-middleware
kubectl rollout status deployment/sds-middleware-app -n sds-middleware
```

## Cleanup

```bash
./k8s/cleanup.sh
```
