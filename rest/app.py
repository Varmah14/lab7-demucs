from flask import Flask, request, jsonify
import redis, base64, os, json

app = Flask(__name__)

r = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True,
)
WORK_QUEUE = os.getenv("WORK_QUEUE", "toWorker")


@app.route("/")
def index():
    return jsonify({"status": "REST API running"})


@app.route("/apiv1/separate", methods=["POST"])
def separate():
    data = request.get_json()
    song_data = data.get("mp3", "")
    song_hash = str(hash(song_data))[-8:]
    r.lpush(WORK_QUEUE, json.dumps({"hash": song_hash, "data": song_data}))
    return jsonify({"hash": song_hash, "reason": "Song enqueued for separation"})


@app.route("/apiv1/queue", methods=["GET"])
def queue():
    qlen = r.llen(WORK_QUEUE)
    return jsonify({"queue": [r.lindex(WORK_QUEUE, i) for i in range(qlen)]})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
