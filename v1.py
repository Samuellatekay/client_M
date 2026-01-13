from flask import Flask, jsonify, abort, request
import os, psutil, platform, threading, time, logging

# Setup logging
logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# Coba inisialisasi Docker, jika gagal, set ke None
try:
    import docker
    Client = docker.from_env()
except Exception as e:
    print(f"Docker tidak tersedia: {e}")
    Client = None

# api key for authentication api ke semetara
API_KEY = os.getenv('API_KEY', '38f863078f79bdc96e199552ba728afd')   

# Global data cache
cached_data = {
    'containers': [],
    'user_status': {},
    'last_update': 0
}
update_interval = 300  # Default 5 menit (300 detik)

# Fungsi update data sekali
def update_data_once():
    try:
        # Update containers
        if Client:
            containers = Client.containers.list(all=True)
            cached_data['containers'] = []
            for container in containers:
                cached_data['containers'].append({
                    'id': container.id,
                    'name': container.name,
                    'image': container.image.tags if container.image.tags else [],
                    'status': container.status,
                    'is_up': container.status == 'running',
                    'ports': container.ports,
                })
        
        # Update user status
        cpu_usage = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        cached_data['user_status'] = {
            'cpu_usage_percent': cpu_usage,
            'memory_total_mb': memory.total // (1024 * 1024),
            'memory_used_mb': memory.used // (1024 * 1024),
            'memory_free_mb': memory.available // (1024 * 1024),
            'disk_total_gb': disk.total // (1024 * 1024 * 1024),
            'disk_used_gb': disk.used // (1024 * 1024 * 1024),
            'disk_free_gb': disk.free // (1024 * 1024 * 1024),
        }
        
        cached_data['last_update'] = time.time()
        print(f"Data updated at {time.ctime()}")
        logging.info("Data cache updated")

# Fungsi update data loop
def update_data():
    while True:
        update_data_once()
        time.sleep(update_interval)

# Start background thread
update_thread = threading.Thread(target=update_data, daemon=True)
update_thread.start()

# Initial update
update_data_once()

# api key for authentication api key semetara
API_KEY = os.getenv('API_KEY', '38f863078f79bdc96e199552ba728afd')   

# cek api key 
@app.before_request
def check_api_key():
    api_key = request.headers.get('mira-api-key')
    if api_key != API_KEY:
        logging.warning(f"Invalid API key attempt: {request.remote_addr}")
        abort(403, description="Forbidden: Invalid API Key")
    logging.info(f"API access from {request.remote_addr}")
        
# Ambil data semua container
@app.route('/api/v1/containers', methods=['GET'])
def get_containers():
    return jsonify({
        "total": len(cached_data['containers']),
        "containers": cached_data['containers'],
        "last_update": time.ctime(cached_data['last_update'])
    })

# Ambil data vm
@app.route('/api/v1/user', methods=['GET'])
def user_status():
    return jsonify({
        **cached_data['user_status'],
        "last_update": time.ctime(cached_data['last_update'])
    })
    
# Fungsi untuk log
def get_auth_log():
    os_type = platform.system()
    if os_type == 'Windows':
        try:
            import win32evtlog
            log = win32evtlog.OpenEventLog(None, 'Security')
            events = []
            flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
            events_read = win32evtlog.ReadEventLog(log, flags, 0)
            for event in events_read[:10]:
                events.append(f"Event ID: {event.EventID}, Time: {event.TimeGenerated}")
            win32evtlog.CloseEventLog(log)
            return "\n".join(events)
        except Exception as e:
            return f"Auth log tidak tersedia: {e}"
    elif os_type == 'Linux':
        try:
            with open('/var/log/auth.log', 'r') as f:
                lines = f.readlines()[-10:]  # Ambil 10 baris terakhir
                return ''.join(lines)
        except Exception as e:
            return f"Auth log tidak tersedia: {e}"
    else:
        return "OS tidak didukung"

def get_system_log():
    try:
        import win32evtlog
        log = win32evtlog.OpenEventLog(None, 'System')
        events = []
        flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
        events_read = win32evtlog.ReadEventLog(log, flags, 0)
        for event in events_read[:10]:
            events.append(f"Event ID: {event.EventID}, Time: {event.TimeGenerated}")
        win32evtlog.CloseEventLog(log)
        return "\n".join(events)
    except Exception as e:
        return f"System log tidak tersedia: {e}"

def get_app_log():
    try:
        with open('app.log', 'r') as f:
            lines = f.readlines()[-20:]  # Ambil 20 baris terakhir
            return ''.join(lines)
    except Exception as e:
        return f"App log tidak tersedia: {e}"
   
# data log user
@app.route('/api/v1/user/logs', methods=['GET'])
def user_log():
    return jsonify({
        "auth_log": get_auth_log(),
        "system_log": get_system_log(),
        "app_log": get_app_log()        
    })

# Set update interval (dalam detik)
@app.route('/api/v1/settings/interval', methods=['POST'])
def set_interval():
    global update_interval
    data = request.get_json()
    if 'interval' in data:
        new_interval = int(data['interval'])
        if new_interval > 0:
            update_interval = new_interval
            return jsonify({"message": f"Update interval set to {new_interval} seconds"})
        else:
            return jsonify({"error": "Interval must be positive"}), 400
    return jsonify({"error": "Missing 'interval' in request"}), 400

# Force update data
@app.route('/api/v1/update', methods=['POST'])
def force_update():
    update_data_once()
    return jsonify({"message": "Data updated", "last_update": time.ctime(cached_data['last_update'])})
    

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7000)




