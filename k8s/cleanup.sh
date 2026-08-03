#!/bin/bash
# Cleanup script for SDS Middleware on Kubernetes

set -e

K8S_CONTEXT="${K8S_CONTEXT:-orbstack}"
KUBECTL=(kubectl --context "$K8S_CONTEXT")

echo "🧹 Cleaning up SDS Middleware from Kubernetes..."

# Delete all resources in the namespace
echo "🗑️  Deleting all resources..."
"${KUBECTL[@]}" delete namespace sds-middleware --ignore-not-found=true

echo "⏳ Waiting for namespace to be deleted..."
"${KUBECTL[@]}" wait --for=delete namespace/sds-middleware --timeout=60s 2>/dev/null || true

echo "✅ Cleanup complete!"
echo ""
echo "💡 To redeploy, run: ./k8s/deploy.sh"
