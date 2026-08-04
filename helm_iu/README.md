# SDS Middleware Helm chart for IU Enterprise Kubernetes

The chart deploys SDS Middleware with configuration injected from an external
Kubernetes Secret. Credentials are never written into Helm release metadata.

Use `../deploy_helm_iu.sh` from the repository root. The script creates or
updates the `sds-middleware-env` Secret from `.env`, optionally configures an
IU registry pull secret, and performs a Helm upgrade using ConfigMaps for Helm
release storage.

Useful overrides:

```bash
NAMESPACE=ua-vpit--research-technologies--rds \
IMAGE_REGISTRY_SERVER=registry.docker.iu.edu \
IMAGE_REPOSITORY=registry.docker.iu.edu/rds/sds-middleware \
IMAGE_TAG=latest \
./deploy_helm_iu.sh
```

To enable ingress, provide an explicit hostname:

```bash
INGRESS_HOST=sds-middleware.apps.iu.edu ./deploy_helm_iu.sh
```
