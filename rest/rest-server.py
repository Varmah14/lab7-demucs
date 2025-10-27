import os, io, json, base64, hashlib, time
from flask import Flask, request, jsonify, send_file, Response
from redis import Redis
from minio import Minio
from minio.error import S3Error

# --- Config (env) ---
REDIS_HOST   = os.getenv("REDIS_HOST", "redis")
REDIS_PORT   = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB     = int(os.getenv("REDIS_DB", "0"))
WORK_QUEUE   = os.getenv("WORK_QUEUE", "toWorker")     # Q1
LOG_LIST     = os.getenv("LOG_LIST", "logging")        # per README
MINIO_HOST   = os.getenv("MINIO_HOST", "minio-proj.minio-ns.svc.cluster.local:9000")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"
MINIO_ACCESS = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET = os.getenv("MINIO_SECRET_KEY")
BUCKET_IN    = os.getenv("BUCKET_IN", "queue")
BUCKET_OUT   = os.getenv("BUCKET_OUT", "output")
MODEL_NAME   = os.getenv("MODEL_NAME", "htdemucs")

# --- Clients ---
app = Flask(__name__)
r = Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
mc = Minio(MINIO_HOST, access_key=MINIO_ACCESS, secret_key=MINIO_SECRET, secure=MINIO_SECURE)

def log(msg: str):
    try:
        r.lpush(LOG_LIST, msg)
    except Exception:
        pass

def ensure_buckets():
    for b in (BUCKET_IN, BUCKET_OUT):
        try:
            if not mc.bucket_exists(b):
                mc.make_bucket(b)
        except Exception as e:
            log(f"bucket error {b}: {e}")

@app.route("/", methods=["GET"])
def root():
    return "<h1>Music Separation Server</h1><p>Use /apiv1/* endpoints.</p>", 200  # GKE ingress health. :contentReference[oaicite:3]{index=3}

@app.route("/apiv1/separate", methods=["POST"])
def separate():
    """
    JSON body:
      {
        "mp3": "<base64-encoded-bytes>",
        "model": "htdemucs",          # optional
        "callback": { "url": "...", "payload": {...} }  # optional
      }
    Returns:
      { "hash": "<songhash>", "reason": "Song enqueued for separation" }
    """
    try:
        body = request.get_json(force=True, silent=False)
    except Exception:
        return jsonify(error="Invalid JSON"), 400

    if not body or "mp3" not in body:
        return jsonify(error="Missing 'mp3' (base64)"), 400

    try:
        mp3_bytes = base64.b64decode(body["mp3"])
    except Exception:
        return jsonify(error="Invalid base64 mp3"), 400

    # hash as song id (shorten for practical object names)
    songhash = hashlib.sha256(mp3_bytes).hexdigest()
    obj_in = f"uploads/{songhash}.mp3"

    ensure_buckets()

    # Idempotent upload (skip if exists)
    try:
        mc.stat_object(BUCKET_IN, obj_in)
    except S3Error:
        mc.put_object(BUCKET_IN, obj_in, io.BytesIO(mp3_bytes), length=len(mp3_bytes), content_type="audio/mpeg")

    payload = {
        "songhash": songhash,
        "object_name": obj_in,
        "model": body.get("model", MODEL_NAME),
        "callback": body.get("callback")  # optional webhook
    }
    r.lpush(WORK_QUEUE, json.dumps(payload))      # Q1: toWorker
    r.lpush(LOG_LIST, f"queued {songhash}")

    return jsonify(hash=songhash, reason="Song enqueued for separation"), 200  # :contentReference[oaicite:4]{index=4}

@app.route("/apiv1/queue", methods=["GET"])
def show_queue():
    # Non-destructive: get a copy via LRANGE
    try:
        items = r.lrange(WORK_QUEUE, 0, -1)
        # show only hashes for friendliness
        hashes = []
        for it in items:
            try:
                hashes.append(json.loads(it).get("songhash"))
            except Exception:
                hashes.append("(unparsed)")
        return jsonify(queue=hashes), 200
    except Exception as e:
        return jsonify(error=str(e)), 500

def _stem_from_request(name: str) -> str:
    """
    REST README mentions 'base.mp3' (likely typo) — accept both 'base' and 'bass'.
    Valid stems we produce: bass, drums, vocals, other.
    """
    name = name.lower()
    if name == "base.mp3":   # tolerate typo from README
        return "bass"
    if name.endswith(".mp3"):
        name = name[:-4]
    if name in ("bass", "drums", "vocals", "other"):
        return name
    return ""  # invalid

@app.route("/apiv1/track/<songhash>/<track>", methods=["GET"])
def get_track(songhash, track):
    stem = _stem_from_request(track)
    if not stem:
        return jsonify(error="track must be one of bass.mp3, vocals.mp3, drums.mp3, other.mp3"), 400
    obj = f"output/{songhash}/{stem}.mp3"
    try:
        resp = mc.get_object(BUCKET_OUT, obj)
        data = resp.read()
        resp.close(); resp.release_conn()
        return send_file(io.BytesIO(data), mimetype="audio/mpeg", as_attachment=True, download_name=f"{stem}.mp3")
    except S3Error:
        return jsonify(error="not found"), 404

@app.route("/apiv1/remove/<songhash>/<track>", methods=["DELETE", "GET"])
def remove_track(songhash, track):
    stem = _stem_from_request(track)
    if not stem:
        return jsonify(error="track must be one of bass.mp3, vocals.mp3, drums.mp3, other.mp3"), 400
    obj = f"output/{songhash}/{stem}.mp3"
    try:
        mc.remove_object(BUCKET_OUT, obj)
        return jsonify(removed=f"{stem}.mp3")
    except S3Error:
        return jsonify(error="not found"), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
