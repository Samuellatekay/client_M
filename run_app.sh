#!/bin/bash


# Script untuk setup dan menjalankan aplikasi Flask dengan virtual environment
# Pastikan Python dan pip sudah terinstall

echo "=== Setup Aplikasi Flask dengan Venv ==="

# Cek Python
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo "Python tidak ditemukan. Install Python terlebih dahulu."
        exit 1
    else
        PYTHON_CMD="python"
    fi
else
    PYTHON_CMD="python3"
fi

echo "Python ditemukan: $($PYTHON_CMD --version)"

# Buat virtual environment jika belum ada
if [ ! -d "venv" ]; then
    echo "Membuat virtual environment..."
    $PYTHON_CMD -m venv venv
    if [ $? -ne 0 ]; then
        echo "Gagal membuat venv."
        exit 1
    fi
fi

# Activate venv
echo "Mengaktifkan virtual environment..."
source venv/bin/activate  # Untuk Linux/Mac
# Jika Windows (Git Bash), uncomment baris berikut dan comment di atas:
# source venv/Scripts/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "Gagal install dependencies."
    exit 1
fi

echo "Dependencies berhasil diinstall."

# Generate dan install service (Linux only)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "Membuat dan menginstall service..."
    
    APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    USER_NAME="$(whoami)"
    
    SERVICE_FILE="/etc/systemd/system/flask-app.service"
    
    sudo bash -c "cat > $SERVICE_FILE << EOF
[Unit]
Description=Flask App Service
After=network.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/python $APP_DIR/v1.py
Restart=always
RestartSec=5
Environment=PATH=$APP_DIR/venv/bin

[Install]
WantedBy=multi-user.target
EOF"
    
    sudo systemctl daemon-reload
    sudo systemctl enable flask-app
    sudo systemctl start flask-app
    
    echo "Service berhasil diinstall dan dijalankan."
    echo "Cek status: sudo systemctl status flask-app"
else
    echo "Service install hanya untuk Linux. Menjalankan server manual..."
    python v1.py
fi

echo "Selesai."