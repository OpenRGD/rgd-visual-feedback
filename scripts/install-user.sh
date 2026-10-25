#!/usr/bin/env bash
set -euo pipefail
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="$HOME/.config/paky-visual-feedback"
CONFIG="$CONFIG_DIR/config.json"
SYSTEMD_DIR="$HOME/.config/systemd/user"
UNIT="$SYSTEMD_DIR/paky01-visual-feedback.service"
CLI="$HOME/.local/bin/paky-led"

command -v python3 >/dev/null || { echo "Python 3 missing"; exit 1; }
command -v systemctl >/dev/null || { echo "systemd missing"; exit 1; }
mkdir -p "$CONFIG_DIR" "$SYSTEMD_DIR" "$HOME/.local/bin"
if [[ ! -f "$CONFIG" ]]; then
  install -m 600 "$SRC/config.example.json" "$CONFIG"
  echo "Configuration created: $CONFIG"
else
  echo "Configuration preserved: $CONFIG"
fi
python3 -m venv "$SRC/.venv"
"$SRC/.venv/bin/python" -m pip install "bleak>=0.20,<3"
PYTHONPATH="$SRC/src" "$SRC/.venv/bin/python" -m unittest discover -s "$SRC/tests" -v
# In systemd unit, % is a specifier; user paths must not contain special chars.
for path in "$SRC" "$CONFIG"; do
  [[ "$path" != *"%"* && "$path" != *$'\n'* && "$path" != *" "* ]] || {
    echo "Unsupported path (spaces / %): $path"; exit 1;
  }
done
cat > "$UNIT" <<UNIT
[Unit]
Description=OpenRGD Paky-01 RGB Visual Feedback (BLE, user mode)

[Service]
Type=simple
Environment=PYTHONPATH=$SRC/src
ExecStart=$SRC/.venv/bin/python -m rgd_visual.server --config $CONFIG
Restart=always
RestartSec=4

[Install]
WantedBy=default.target
UNIT
printf '#!/usr/bin/env sh\nexport PYTHONPATH="%s/src"\nexec "%s/.venv/bin/python" -m rgd_visual.cli "$@"\n' "$SRC" "$SRC" > "$CLI"
chmod 755 "$CLI"
systemctl --user daemon-reload
systemctl --user enable --now paky01-visual-feedback.service
echo
printf 'Installed. Try: %s status\n' "$CLI"
printf 'Then: %s listening\n' "$CLI"
echo 'Logs: journalctl --user -u paky01-visual-feedback -f'
echo 'Note: starts when your user systemd session is active (not necessarily before login).'
