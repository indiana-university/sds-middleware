#!/bin/bash
# Quick deployment script for SDS Middleware on Kubernetes (OrbStack)

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
K8S_CONTEXT="${K8S_CONTEXT:-orbstack}"
KUBECTL=(kubectl --context "$K8S_CONTEXT")

echo "🚀 Starting SDS Middleware deployment to Kubernetes..."

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl not found. Please install OrbStack and enable Kubernetes."
    exit 1
fi

if ! "${KUBECTL[@]}" cluster-info &> /dev/null; then
    echo "❌ Kubernetes context '$K8S_CONTEXT' is unavailable. Enable Kubernetes in OrbStack and try again."
    exit 1
fi

# Check if Docker image exists
if ! docker images | grep -q "sds-middleware"; then
    echo "📦 Building Docker image..."
    docker build -t sds-middleware:latest .
else
    echo "✅ Docker image found"
fi

# Create namespace
echo "📁 Creating namespace..."
"${KUBECTL[@]}" apply -f k8s/namespace.yaml

if [[ ! -f .env ]]; then
    echo "❌ Missing .env. Copy .env.example to .env and set the remote database values first."
    exit 1
fi

# Keep runtime configuration, including remote database credentials, out of Git.
echo "🔐 Creating runtime configuration secret from .env..."
"${KUBECTL[@]}" create secret generic sds-runtime-env \
    --from-env-file=.env \
    --namespace=sds-middleware \
    --dry-run=client \
    --output=yaml | "${KUBECTL[@]}" apply -f -

# Deploy Application
echo "🌐 Deploying application..."
"${KUBECTL[@]}" apply -f k8s/app.yaml

echo "⏳ Waiting for application to be ready..."
"${KUBECTL[@]}" wait --for=condition=ready pod -l app=sds-middleware -n sds-middleware --timeout=120s

# Get service information
echo ""
echo "✅ Deployment complete!"
echo ""
echo "📊 Service Status:"
"${KUBECTL[@]}" get services -n sds-middleware

echo ""
echo "🔗 Access the application at:"
echo "   Main App:            http://localhost:8080"
echo "   Database status:     http://localhost:8080/config/db (requires client secret)"
echo ""
echo "📝 View logs with:"
echo "   kubectl --context $K8S_CONTEXT logs -n sds-middleware -l app=sds-middleware --tail=100 -f"
echo ""
echo "🔍 Check status with:"
echo "   kubectl --context $K8S_CONTEXT get all -n sds-middleware"
