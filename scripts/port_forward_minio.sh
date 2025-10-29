#!/usr/bin/env bash
kubectl -n msas port-forward svc/myminio-proj 9000:9000 9001:9001
# Console: http://127.0.0.1:9001  (minio / minio123)
