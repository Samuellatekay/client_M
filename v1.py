from flask import Flask, jsonify, abort, request
import os, psutil, threading, time

app = Flask(__name__)

# =============================
# Docker Client (Safe Init)
# =============================
try:
    import docker
    docker_client = docker.from_env()
except Exception:
    docker_client = None

# =============================
# API KEY
# =============================
API_KEY = os.getenv('API_KEY', '38f863078f79bdc96e199552ba728afd')

# =============================
# Global Cache + Lock
# =============================
cached_data = {
    'containers': [],
    'host_status': {},
    'last_update': 0
}

data_lock = threading.Lock()
update_interval = 10  # detik

# =============================
# Update Data Once
# =============================
def update_data_once():
    with data_lock:
        containers_data = []

        if docker_client:
            containers = docker_client.containers.list(all=True)

            for c in containers:
                cpu_percent = 0.0
                mem_usage_mb = 0.0
                mem_limit_mb = 0.0

                if c.status == "running":
                    try:
                        stats = c.stats(stream=False)

                        cpu_delta = (
                            stats["cpu_stats"]["cpu_usage"]["total_usage"]
                            - stats["precpu_stats"]["cpu_usage"]["total_usage"]
                        )

                        system_delta = (
                            stats["cpu_stats"]["system_cpu_usage"]
                            - stats["precpu_stats"]["system_cpu_usage"]
                        )

                        if system_delta > 0:
                            cpu_percent = (
                                cpu_delta / system_delta
                            ) * len(
                                stats["cpu_stats"]["cpu_usage"].get(
                                    "percpu_usage", []
                                )
                            ) * 100.0

                        mem_usage_mb = stats["memory_stats"]["usage"] / (1024 ** 2)
                        mem_limit_mb = stats["memory_stats"]["limit"] / (1024 ** 2)

                    except Exception:
                        pass

                containers_data.append({
                    "id": c.id[:12],
                    "name": c.name,
                    "image": c.image.tags or [],
                    "status": c.status,
                    "is_up": c.status == "running",
                    "ports": c.ports,
                    "restart_count": c.attrs.get("RestartCount", 0),
                    "cpu_percent": round(cpu_percent, 2),
                    "memory_usage_mb": round(mem_usage_mb, 2),
                    "memory_limit_mb": round(mem_limit_mb, 2)
                })

        cached_data["containers"] = containers_data

        # ---------- Host Monitoring ----------
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        cached_data["host_status"] = {
            "cpu_usage_percent": cpu,
            "memory_total_mb": mem.total // (1024 ** 2),
            "memory_used_mb": mem.used // (1024 ** 2),
            "memory_free_mb": mem.available // (1024 ** 2),
            "disk_total_gb": disk.total // (1024 ** 3),
            "disk_used_gb": disk.used // (1024 ** 3),
            "disk_free_gb": disk.free // (1024 ** 3)
        }

        cached_data["last_update"] = time.time()

# =============================
# Background Thread
# =============================
def update_loop():
    while True:
        update_data_once()
        time.sleep(update_interval)

threading.Thread(target=update_loop, daemon=True).start()
update_data_once()

# =============================
# API KEY Middleware
# =============================
@app.before_request
def check_api_key():
    if request.endpoint == 'health_check':
        return

    api_key = request.headers.get('mira-api-key')
    if api_key != API_KEY:
        abort(403, description="Forbidden: Invalid API Key")

# =============================
# Health Check
# =============================
@app.route('/health')
def health_check():
    return jsonify({"status": "ok"})

# =============================
# API: Containers
# =============================
@app.route('/api/v1/containers', methods=['GET'])
def get_containers():
    with data_lock:
        return jsonify({
            "total": len(cached_data["containers"]),
            "containers": cached_data["containers"],
            "last_update": time.ctime(cached_data["last_update"])
        })

# =============================
# API: Host Status
# =============================
@app.route('/api/v1/host', methods=['GET'])
def get_host_status():
    with data_lock:
        return jsonify({
            **cached_data["host_status"],
            "last_update": time.ctime(cached_data["last_update"])
        })

# =============================
# Run App
# =============================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7000)
