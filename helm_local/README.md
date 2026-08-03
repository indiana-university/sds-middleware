# SDS Middleware Helm chart (OrbStack)

This chart deploys SDS Middleware using the locally built
`sds-middleware:latest` image and a pre-existing Kubernetes Secret containing
the application `.env` settings.

## Deploy on OrbStack

```bash
docker build -t sds-middleware:latest .
kubectl --context orbstack create namespace sds-middleware --dry-run=client -o yaml | kubectl --context orbstack apply -f -
kubectl --context orbstack create secret generic sds-runtime-env \
  --from-env-file=.env -n sds-middleware --dry-run=client -o yaml | kubectl --context orbstack apply -f -
helm upgrade --install sds-middleware-local ./helm_local \
  --namespace sds-middleware --kube-context orbstack --wait --timeout 120s
helm test sds-middleware-local --namespace sds-middleware --kube-context orbstack
```

The chart's readiness probe and Helm test both call authenticated `/config/db`,
so a successful install confirms remote database connectivity.

Remove the release with:

```bash
helm uninstall sds-middleware-local --namespace sds-middleware --kube-context orbstack
```
