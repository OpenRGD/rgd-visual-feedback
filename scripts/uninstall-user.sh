#!/usr/bin/env bash
set -euo pipefail
systemctl --user disable --now paky01-visual-feedback.service || true
rm -f "$HOME/.config/systemd/user/paky01-visual-feedback.service"
rm -f "$HOME/.local/bin/paky-led"
systemctl --user daemon-reload
printf 'Stopped/removed user service and CLI. Your config and source files were preserved.\n'
