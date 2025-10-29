#!/usr/bin/env bash
set -euo pipefail
kubectl apply -f k8s/00-namespace.yaml
kubectl config set-context --current --namespace=msas

kubectl -n msas create secret generic minio-credentials \
  --from-literal=MINIO_ACCESS_KEY=minio \
  --from-literal=MINIO_SECRET_KEY=minio123 \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f k8s/01-redis.yaml
kubectl apply -f k8s/02-minio.yaml
kubectl apply -f k8s/03-rest.yaml
kubectl apply -f k8s/04-worker.yaml

kubectl -n msas get pods,svc
