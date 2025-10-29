#!/usr/bin/env bash
kubectl -n msas port-forward svc/rest-service 5000:5000
# REST: http://127.0.0.1:5000/
