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

# Coba inisialisasi boto3 untuk AWS
try:
    import boto3
    AWS_AVAILABLE = True
except ImportError:
    print("boto3 tidak tersedia, AWS checks disabled.")
    AWS_AVAILABLE = False

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
            'is_up': container.status == 'running',  # Tambahan: true jika running
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

# AWS misconfiguration dan policy checks
@app.route('/api/v1/aws/checks', methods=['GET'])
def aws_checks():
    if not AWS_AVAILABLE:
        return jsonify({"error": "AWS boto3 tidak tersedia"}), 503
    
    try:
        # Inisialisasi clients
        iam = boto3.client('iam')
        ec2 = boto3.client('ec2')
        s3 = boto3.client('s3')
        
        checks = {}
        
        # Check IAM policies
        checks['iam_policies'] = []
        policies = iam.list_policies(Scope='Local')['Policies']
        for policy in policies[:5]:  # Limit to 5
            checks['iam_policies'].append({
                'name': policy['PolicyName'],
                'arn': policy['Arn'],
                'attached': len(iam.list_entities_for_policy(PolicyArn=policy['Arn'])['PolicyGroups']) > 0
            })
        
        # Check S3 buckets for misconfigurations
        checks['s3_buckets'] = []
        buckets = s3.list_buckets()['Buckets']
        for bucket in buckets[:5]:  # Limit to 5
            bucket_name = bucket['Name']
            try:
                # Check public access
                public = s3.get_bucket_public_access_block(Bucket=bucket_name)
                checks['s3_buckets'].append({
                    'name': bucket_name,
                    'public_access_block': public.get('PublicAccessBlockConfiguration', {})
                })
            except Exception as e:
                checks['s3_buckets'].append({
                    'name': bucket_name,
                    'error': str(e)
                })
        
        # Check EC2 instances
        checks['ec2_instances'] = []
        instances = ec2.describe_instances()['Reservations']
        for reservation in instances[:3]:  # Limit
            for instance in reservation['Instances']:
                checks['ec2_instances'].append({
                    'id': instance['InstanceId'],
                    'state': instance['State']['Name'],
                    'public_ip': instance.get('PublicIpAddress', 'None'),
                    'security_groups': [sg['GroupName'] for sg in instance['SecurityGroups']]
                })
        
        return jsonify(checks)
    
    except Exception as e:
        return jsonify({"error": f"AWS check failed: {str(e)}"}), 500




