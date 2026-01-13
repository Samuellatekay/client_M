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

# Jalankan server
echo "Menjalankan server Flask..."
python v1.py

echo "Server berhenti."