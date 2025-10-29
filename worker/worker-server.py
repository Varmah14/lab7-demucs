import redis, os, json, base64, tempfile, subprocess
from minio import Minio

r = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True,
)

client = Minio(
    os.getenv("MINIO_HOST", "myminio-proj:9000"),
    access_key=os.getenv("MINIO_ACCESS_KEY", "minio"),
    secret_key=os.getenv("MINIO_SECRET_KEY", "minio123"),
    secure=False,
)

BUCKET_IN = os.getenv("BUCKET_IN", "queue")
BUCKET_OUT = os.getenv("BUCKET_OUT", "output")


def process_song(song_hash, b64data):
    data = base64.b64decode(b64data)
    tmpin = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmpin.write(data)
    tmpin.close()
    subprocess.run(["demucs", tmpin.name, "-o", "/tmp/out"], check=False)
    outdir = "/tmp/out/htdemucs"
    for file in os.listdir(outdir):
        client.fput_object(BUCKET_OUT, f"{song_hash}-{file}", f"{outdir}/{file}")
    print(f"✅ Uploaded separated tracks for {song_hash}")


def main():
    print("Worker started, waiting for tasks...")
    while True:
        task = r.blpop(os.getenv("WORK_QUEUE", "toWorker"), timeout=10)
        if not task:
            continue
        payload = json.loads(task[1])
        process_song(payload["hash"], payload["data"])


if __name__ == "__main__":
    main()
