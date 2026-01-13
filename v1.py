from flask import Flask, jsonify, abort, request
import os, psutil, threading, time, logging

# =============================
# Setup Logging
# =============================
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

app = Flask(__name__)

# =============================
# Docker Client (Safe Init)
# =============================
try:
    import docker
    docker_client = docker.from_env()
except Exception as e:
    logging.warning(f"Docker tidak tersedia: {e}")
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
    'user_status': {},
    'last_update': 0
}

data_lock = threading.Lock()
update_interval = 300  # 5 menit

# =============================
# Update Data Once
# =============================
def update_data_once():
    try:
        with data_lock:
            # ---------- Docker Containers ----------
            containers_data = []
            if docker_client:
                try:
                    containers = docker_client.containers.list(all=True)
                    for c in containers:
                        containers_data.append({
                            'id': c.id,
                            'name': c.name,
                            'image': c.image.tags or [],
                            'status': c.status,
                            'is_up': c.status == 'running',
                            'ports': c.ports,
                            'jumlah_restart': c.attrs.get('RestartCount', 0)
                        })
                except Exception as e:
                    logging.error(f"Error docker scan: {e}")

            cached_data['containers'] = containers_data

            # ---------- System Status ----------
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            cached_data['user_status'] = {
                'cpu_usage_percent': cpu,
                'memory_total_mb': mem.total // (1024 ** 2),
                'memory_used_mb': mem.used // (1024 ** 2),
                'memory_free_mb': mem.available // (1024 ** 2),
                'disk_total_gb': disk.total // (1024 ** 3),
                'disk_used_gb': disk.used // (1024 ** 3),
                'disk_free_gb': disk.free // (1024 ** 3),
            }

            cached_data['last_update'] = time.time()

        logging.info("Data cache berhasil diupdate")

    except Exception as e:
        logging.error(f"Update error: {e}")

# =============================
# Background Thread
# =============================
def update_loop():
    while True:
        update_data_once()
        time.sleep(update_interval)

threading.Thread(target=update_loop, daemon=True).start()

# Initial load
update_data_once()

# =============================
# API KEY Middleware
# =============================
@app.before_request
def check_api_key():
    if request.endpoint in ['health_check']:
        return

    api_key = request.headers.get('mira-api-key')
    if api_key != API_KEY:
        logging.warning(f"Unauthorized access from {request.remote_addr}")
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
            "total": len(cached_data['containers']),
            "containers": cached_data['containers'],
            "last_update": time.ctime(cached_data['last_update'])
        })

# =============================
# API: System Status
# =============================
@app.route('/api/v1/user', methods=['GET'])
def get_user_status():
    with data_lock:
        return jsonify({
            **cached_data['user_status'],
            "last_update": time.ctime(cached_data['last_update'])
        })

# =============================
# Logs Functions
# =============================
def get_auth_log():
    try:
        with open('/var/log/auth.log', 'r') as f:
            return ''.join(f.readlines()[-10:])
    except Exception as e:
        return f"Auth log error: {e}"

def get_app_log():
    try:
        with open('app.log', 'r') as f:
            return ''.join(f.readlines()[-20:])
    except Exception as e:
        return f"App log error: {e}"

# =============================
# API: Logs
# =============================
@app.route('/api/v1/user/logs', methods=['GET'])
def get_logs():
    return jsonify({
        "auth_log": get_auth_log(),
        "app_log": get_app_log()
    })

# =============================
# Run App
# =============================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7000)
# =============================
