#!/usr/bin/env bash
# BTR bot: installs everything on a fresh Ubuntu 24.04 server and starts it as a service.
# Usage (on the server, in the project folder):  bash install.sh
set -euo pipefail
cd "$(dirname "$0")"
DIR="$(pwd)"
USER_NAME="$(whoami)"

echo "== System packages"
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip ffmpeg fonts-dejavu-core curl unzip

echo "== Deno (JavaScript runtime yt-dlp needs for YouTube)"
if ! command -v deno >/dev/null; then
  curl -fsSL https://deno.land/install.sh | sh -s -- -y
  sudo ln -sf "$HOME/.deno/bin/deno" /usr/local/bin/deno
fi

echo "== Python environment"
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
python -m playwright install --with-deps chromium

echo "== Models"
mkdir -p models secrets data
[ -s models/big-lama.pt ] || curl -L -o models/big-lama.pt \
  https://github.com/enesmsahin/simple-lama-inpainting/releases/download/v0.1.0/big-lama.pt
[ -s models/face_detection_yunet_2023mar.onnx ] || curl -L -o models/face_detection_yunet_2023mar.onnx \
  https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
[ -s models/face_recognition_sface_2021dec.onnx ] || curl -L -o models/face_recognition_sface_2021dec.onnx \
  https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx
python -c "from rembg import new_session; new_session('isnet-general-use'); print('rembg model ready')"

[ -f .env ] || cp .env.example .env

echo "== Service"
sudo tee /etc/systemd/system/btr-bot.service >/dev/null <<EOF
[Unit]
Description=Break The Routine bot
After=network-online.target
Wants=network-online.target

[Service]
User=${USER_NAME}
WorkingDirectory=${DIR}
ExecStartPre=${DIR}/.venv/bin/pip install -q -U "yt-dlp[default]"
ExecStart=${DIR}/.venv/bin/python -m btrbot
Restart=always
RestartSec=20
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable btr-bot

echo "Done. The bot is started by the GitHub workflow (or: systemctl restart btr-bot)."
