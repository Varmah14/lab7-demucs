# 🎵 Lab 7 – Music Separation as a Service (MSaaS)

**Course:** CSCI 4253/5253 – Datacenter-Scale Computing  
**Student:** Mahendra Varma Vaddi  
**University:** University of Colorado Boulder  
**Instructor:** Dr. Goodman

---

## 📘 Overview

This lab implements a **microservice-based music-separation platform** using **Kubernetes**.  
The system provides an HTTP REST API to upload MP3 files, which are then separated into stems (vocals, drums, bass, other) using Facebook’s **Demucs** model.

Each component runs in a separate container managed by Kubernetes. Communication between services is handled via **Redis queues**, and separated outputs are stored in **MinIO object storage**.

---

## 🧩 Architecture Overview

### Components

| Component          | Function                                                                     | Technology                   |
| ------------------ | ---------------------------------------------------------------------------- | ---------------------------- |
| **REST Service**   | Accepts API requests (`/apiv1/separate`) and enqueues jobs to Redis          | Flask (Python)               |
| **Redis Server**   | Message queue between REST and Worker                                        | Redis                        |
| **Worker Service** | Pulls jobs from Redis, downloads MP3s, runs Demucs, uploads outputs to MinIO | Python + TorchAudio + Demucs |
| **MinIO Server**   | Stores input/output objects (“queue” and “output” buckets)                   | MinIO (S3-compatible)        |

### Visual Architecture Diagram

## ![Architecture Diagram](architecture diagram.txt)
