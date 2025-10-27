# worker/worker-server.py
import os, io, json, time, tempfile, subprocess, shutil, hashlib, requests
from redis import Redis
from minio import Minio
from minio.error import S3Error

# --- Config (env) ---
REDIS_HOST   = os.getenv("REDIS_HOST", "redis")
REDIS_PORT   = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB     = int(os.getenv("REDIS_DB", "0"))
WORK_QUEUE   = os.getenv("WORK_QUEUE", "toWorker")
LOG_LIST     = os.getenv("LOG_LIST", "logging")

MINIO_HOST   = os.getenv("MINIO_HOST", "minio-proj.minio-ns.svc.cluster.local:9000")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"
MINIO_ACCESS = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET = os.getenv("MINIO_SECRET_KEY")
BUCKET_IN    = os.getenv("BUCKET_IN", "queue")
BUCKET_OUT   = os.getenv("BUCKET_OUT", "output")
MODEL_NAME   = os.getenv("MODEL_NAME", "htdemucs")  # any demucs model

STEMS = ("bass", "drums", "vocals", "other")  # target stems

# --- Clients ---
r  = Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
mc = Minio(MINIO_HOST, access_key=MINIO_ACCESS, secret_key=MINIO_SECRET, secure=MINIO_SECURE)

def log(msg: str):
    try:
        r.lpush(LOG_LIST, msg)
    except Exception:
        pass

def download_obj(bucket, obj, dst):
    resp = mc.get_object(bucket, obj)
    with open(dst, "wb") as f:
        shutil.copyfileobj(resp, f)
    resp.close(); resp.release_conn()

def upload_obj(bucket, obj, path):
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        mc.put_object(bucket, obj, f, size, content_type="audio/mpeg")

def run_demucs(input_path, out_dir, model):
    # Use CLI as suggested by README (simple & robust). :contentReference[oaicite:7]{index=7}
    # --mp3 outputs mp3 files directly to save ffmpeg step
    cmd = f'python3 -m demucs.separate -n {model} --mp3 --out "{out_dir}" "{input_path}"'
    subprocess.check_call(cmd, shell=True)

def maybe_callback(cb, songhash, status, detail=None):
    if not cb or not isinstance(cb, dict) or "url" not in cb:
        return
    payload = cb.get("payload", {})
    payload.update({"songhash": songhash, "status": status})
    if detail:
        payload["detail"] = detail
    try:
        requests.post(cb["url"], json=payload, timeout=5)
    except Exception:
        pass  # best-effort

def main():
    log("worker: started")
    while True:
        item = r.blpop(WORK_QUEUE, timeout=5)
        if not item:
            continue
        _, job_json = item
        try:
            job = json.loads(job_json)
        except Exception as e:
            log(f"worker: bad job json {e}")
            continue

        songhash   = job.get("songhash")
        object_name= job.get("object_name")
        model      = job.get("model", MODEL_NAME)
        callback   = job.get("callback")

        if not songhash or not object_name:
            log("worker: missing songhash/object_name")
            continue

        log(f"worker: processing {songhash}")
        with tempfile.TemporaryDirectory() as td:
            in_path = os.path.join(td, "in.mp3")
            try:
                download_obj(BUCKET_IN, object_name, in_path)
            except Exception as e:
                log(f"worker: download failed {e}")
                maybe_callback(callback, songhash, "error", "download_failed")
                continue

            try:
                out_root = os.path.join(td, "out")
                os.makedirs(out_root, exist_ok=True)
                run_demucs(in_path, out_root, model)
            except subprocess.CalledProcessError as e:
                log(f"worker: demucs failed {e}")
                maybe_callback(callback, songhash, "error", "demucs_failed")
                continue

            # demucs outputs: out_root/<model>/<basename>/{stems}.mp3
            base = os.path.splitext(os.path.basename(in_path))[0]
            demucs_dir = os.path.join(out_root, model, base)

            uploaded = []
            for stem in STEMS:
                src = os.path.join(demucs_dir, f"{stem}.mp3")
                if not os.path.exists(src):
                    continue
                dst = f"output/{songhash}/{stem}.mp3"
                try:
                    upload_obj(BUCKET_OUT, dst, src)
                    uploaded.append(stem)
                except Exception as e:
                    log(f"worker: upload {stem} failed {e}")

            log(f"worker: done {songhash}; stems={uploaded}")
            maybe_callback(callback, songhash, "done", {"stems": uploaded})

if __name__ == "__main__":
    main()

