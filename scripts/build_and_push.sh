#!/usr/bin/env bash
set -euo pipefail

PROJECT="${PROJECT:-demucs-lab}"
REGION="us-central1"

gcloud config set project "$PROJECT"
gcloud auth configure-docker "$REGION-docker.pkg.dev"

gcloud builds submit --tag "$REGION-docker.pkg.dev/$PROJECT/msas/msas-rest:v1"   ./rest
gcloud builds submit --tag "$REGION-docker.pkg.dev/$PROJECT/msas/msas-worker:v2" ./worker

gcloud artifacts docker images list "$REGION-docker.pkg.dev/$PROJECT/msas"
