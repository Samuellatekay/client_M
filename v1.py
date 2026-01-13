from flask import Flask, jsonify, abort, request
import os, psutil
import platform

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

# cek api key 
@app.before_request
def check_api_key():
    api_key = request.headers.get('mira-api-key')
    print(f"Received API key: {api_key}")  # Debug
    if api_key != API_KEY:
        abort(403, description="Forbidden: Invalid API Key")
        
# Ambil data semua container
@app.route('/api/v1/containers', methods=['GET'])
def get_containers():
    if Client is None:
        return jsonify({"error": "Docker tidak tersedia"}), 503
    
    containers = Client.containers.list(all=True)
    data_container = []
    
    for container in containers:
        data_container.append({
            'id': container.id,
            'name': container.name,
            'image': container.image.tags if container.image.tags else [],
            'status': container.status,
            'ports': container.ports,
            
        })
    return jsonify({
        "total": len(data_container),
        "containers": data_container

        
    })

# Ambil data vm
@app.route('/api/v1/user', methods=['GET'])
def user_status():
    cpu_usage = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    return jsonify({
        'cpu_usage_percent': cpu_usage,
        'memory_total_mb': memory.total // (1024 * 1024),
        'memory_used_mb': memory.used // (1024 * 1024),
        'memory_free_mb': memory.available // (1024 * 1024),
        'disk_total_gb': disk.total // (1024 * 1024 * 1024),
        'disk_used_gb': disk.used // (1024 * 1024 * 1024),
        'disk_free_gb': disk.free // (1024 * 1024 * 1024),
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
   
# data log user
@app.route('/api/v1/user/logs', methods=['GET'])
def user_log():
    return jsonify({
        "auth_log": get_auth_log(),
        "system_log": get_system_log()        
    })
    

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7000)


