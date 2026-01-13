from flask import Flask, jsonify, abort, request
import docker
import os
import threading
import time
import psutil

app = Flask(__name__)

# =============================
# Docker Client
# =============================
try:
    docker_client = docker.from_env()
except Exception as e:
    docker_client = None
    print("Docker error:", e)

# =============================
# API KEY
# =============================
API_KEY = os.getenv("API_KEY", "38f863078f79bdc96e199552ba728afd")

# =============================
# Cache + Lock
# =============================
cached_data = {
    "containers": [],
    "system": {},
    "last_update": ""
}

lock = threading.Lock()
INTERVAL = 5  # detik

# =============================
# Helper: CPU %
# =============================
def calculate_cpu_percent(stats):
    try:
        cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                    stats["precpu_stats"]["cpu_usage"]["total_usage"]

        system_delta = stats["cpu_stats"]["system_cpu_usage"] - \
                       stats["precpu_stats"]["system_cpu_usage"]

        cpu_count = len(stats["cpu_stats"]["cpu_usage"].get("percpu_usage", []))

        if system_delta > 0:
            return round((cpu_delta / system_delta) * cpu_count * 100, 2)
    except Exception:
        pass
    return 0.0

# =============================
# Update Data
# =============================
def update_data():
    while True:
        with lock:
            result = []

            if docker_client:
                for c in docker_client.containers.list(all=True):
                    try:
                        c.reload()
                        state = c.attrs["State"]
                        status = state.get("Status", "unknown")
                        restart_count = state.get("RestartCount", 0)

                        # ---------- STATUS ----------
                        container_state = "UP" if status == "running" else "DOWN"

                        cpu = 0.0
                        mem_used = 0.0
                        mem_limit = 0.0

                        if status == "running":
                            stats = c.stats(stream=False)
                            cpu = calculate_cpu_percent(stats)
                            mem_used = stats["memory_stats"]["usage"] / (1024 ** 2)
                            mem_limit = stats["memory_stats"]["limit"] / (1024 ** 2)

                        result.append({
                            "id": c.id[:12],
                            "name": c.name,
                            "image": c.image.tags or [],
                            "docker_status": status,
                            "state": container_state,
                            "cpu_percent": cpu,
                            "memory_usage_mb": round(mem_used, 2),
                            "memory_limit_mb": round(mem_limit, 2),
                            "restart_count": restart_count,
                            "ports": c.ports
                        })

                    except Exception as e:
                        result.append({
                            "id": c.id[:12],
                            "name": c.name,
                            "state": "ERROR",
                            "error": str(e)
                        })

            cached_data["containers"] = result
            cached_data["system"] = {
                "cpu_usage_percent": psutil.cpu_percent(),
                "memory_usage_percent": psutil.virtual_memory().percent,
                "disk_usage_percent": psutil.disk_usage("/").percent
            }
            cached_data["last_update"] = time.ctime()

        time.sleep(INTERVAL)

# =============================
# Background Thread
# =============================
threading.Thread(target=update_data, daemon=True).start()

# =============================
# API KEY Middleware
# =============================
@app.before_request
def check_api_key():
    if request.endpoint == "health":
        return
    if request.headers.get("mira-api-key") != API_KEY:
        abort(403)

# =============================
# Health
# =============================
@app.route("/health")
def health():
    return jsonify({"status": "ok"})

# =============================
# Containers API
# =============================
@app.route("/api/v1/containers")
def containers():
    with lock:
        return jsonify({
            "total": len(cached_data["containers"]),
            "containers": cached_data["containers"],
            "last_update": cached_data["last_update"]
        })

# =============================
# System API
# =============================
@app.route("/api/v1/system")
def system():
    with lock:
        return jsonify({
            **cached_data["system"],
            "last_update": cached_data["last_update"]
        })

# =============================
# Run
# =============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7000)
