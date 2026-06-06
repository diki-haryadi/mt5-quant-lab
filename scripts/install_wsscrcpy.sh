#!/bin/bash
# install ws-scrcpy (web scrcpy) di CT160 + konek redroid lokal. Idempoten-ish. Log ke /var/log/wsscrcpy.log
exec > >(tee -a /var/log/wsscrcpy.log) 2>&1
set -x
export DEBIAN_FRONTEND=noninteractive
echo "=== STEP apt $(date) ==="
apt-get update -y
apt-get install -y nodejs npm git build-essential python3 || { echo APT_FAIL; exit 1; }
node -v; npm -v
echo "=== STEP clone ==="
cd /opt
[ -d ws-scrcpy/.git ] || git clone --depth 1 https://github.com/NetrisTV/ws-scrcpy.git
cd /opt/ws-scrcpy
echo "=== STEP npm install ==="
npm install --no-audit --no-fund || { echo NPM_INSTALL_FAIL; exit 1; }
echo "=== STEP build (dist) ==="
npm run dist 2>&1 || npm run build 2>&1 || true
RUNCMD=""
if [ -f dist/index.js ]; then RUNCMD="/usr/bin/node /opt/ws-scrcpy/dist/index.js"; else RUNCMD="/usr/bin/npm --prefix /opt/ws-scrcpy start"; fi
echo "RUNCMD=$RUNCMD"
echo "=== STEP systemd ==="
cat > /etc/systemd/system/ws-scrcpy.service <<EOF
[Unit]
Description=ws-scrcpy web android (NetrisTV)
After=network-online.target docker.service
[Service]
WorkingDirectory=/opt/ws-scrcpy
ExecStartPre=-/usr/bin/adb connect 127.0.0.1:5555
ExecStart=$RUNCMD
Restart=always
RestartSec=10
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
adb connect 127.0.0.1:5555 || true
systemctl enable --now ws-scrcpy
sleep 6
echo "=== STEP verify ==="
systemctl is-active ws-scrcpy
ss -ltnp 2>/dev/null | grep -E ":8000|:8886" || netstat -ltnp 2>/dev/null | grep -E ":8000|:8886" || echo "PORT not found yet"
echo "INSTALL_DONE $(date)"
