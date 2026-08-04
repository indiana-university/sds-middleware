# SDS Middleware Helm chart for IU Enterprise Kubernetes

The chart deploys SDS Middleware with configuration injected from an external
Kubernetes Secret. Credentials are never written into Helm release metadata.

The IU namespace may allow creating Secrets without allowing users to read or
update them. Accordingly, the deployment script creates `sds-middleware-env`
only when it is absent and reuses it thereafter. Have a namespace administrator
rotate the Secret when credentials change.

IU requires CPU and memory requests for every container. The chart sets both
requests to `0`, per IU guidance. Limits still count against the namespace
quota, so the limits of SDS Middleware and SDS Omeka must fit within `team`'s
`limits.cpu` and `limits.memory` totals.

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
