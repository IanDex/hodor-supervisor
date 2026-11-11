#!/bin/bash
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.hodor-sup"
PY="$(command -v python3)"; [ -n "$PY" ] || { echo "Falta python3."; exit 1; }
command -v aws >/dev/null || echo "Aviso: no encuentro el AWS CLI (aws). Sin él no podrás aprobar desde el panel."
mkdir -p "$DEST/kit"
if [ -d "$DIR/.git" ]; then echo "$DIR" > "$DEST/repo"; else echo "Aviso: no instalaste desde el clon de hodor-supervisor; Buscar actualización no va a poder actualizarlo."; fi
if [ ! -f "$DEST/config.json" ]; then
  if [ -f "$DIR/config.json" ]; then cp "$DIR/config.json" "$DEST/config.json"; else cp "$DIR/config.ejemplo.json" "$DEST/config.json"; fi
  chmod 600 "$DEST/config.json"
  echo "Dejé tu configuración en $DEST/config.json: pon ahí tu token y tu perfil de AWS."
fi
cp "$DIR/servidor.py" "$DIR/panel.html" "$DIR/VERSION" "$DEST/kit/"
"$PY" "$DEST/kit/servidor.py" --estado || true
PANEL="http://127.0.0.1:7790"
RUTA="$(dirname "$(command -v aws 2>/dev/null || echo /usr/local/bin/aws)"):/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"

if [ "$(uname)" = "Darwin" ]; then
  PLIST="$HOME/Library/LaunchAgents/com.global66.hodor-sup.plist"
  cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.global66.hodor-sup</string>
  <key>ProgramArguments</key><array><string>$PY</string><string>$DEST/kit/servidor.py</string><string>--sin-navegador</string></array>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>$RUTA</string></dict>
  <key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$DEST/servidor.log</string>
  <key>StandardErrorPath</key><string>$DEST/servidor.log</string>
</dict></plist>
PL
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load "$PLIST"
  sleep 2; open "$PANEL"
  echo "Listo: Hodor Supervisor corre en segundo plano. Tu panel: $PANEL · Log: $DEST/servidor.log"
  exit 0
fi

pkill -f "$DEST/kit/servidor.py" 2>/dev/null || true
if [ -d /run/systemd/system ] && systemctl --user show-environment >/dev/null 2>&1; then
  mkdir -p "$HOME/.config/systemd/user"
  cat > "$HOME/.config/systemd/user/hodor-sup.service" <<UN
[Unit]
Description=Hodor Supervisor

[Service]
ExecStart=$PY $DEST/kit/servidor.py --sin-navegador
Environment=PATH=$RUTA
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
UN
  systemctl --user daemon-reload
  systemctl --user enable --now hodor-sup.service
  systemctl --user restart hodor-sup.service
else
  PATH="$RUTA:$PATH" nohup "$PY" "$DEST/kit/servidor.py" --sin-navegador >>"$DEST/servidor.log" 2>&1 &
fi
sleep 2
if command -v cmd.exe >/dev/null 2>&1; then (cd /mnt/c && cmd.exe /c start "" "$PANEL") >/dev/null 2>&1 || true
elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$PANEL" >/dev/null 2>&1 || true; fi
echo "Listo: Hodor Supervisor corre en segundo plano. Tu panel: $PANEL · Log: $DEST/servidor.log"
