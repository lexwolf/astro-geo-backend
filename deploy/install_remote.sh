#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/opt/astrogeo}"
RELEASES_DIR="${RELEASES_DIR:-${APP_ROOT}/releases}"
CURRENT_LINK="${CURRENT_LINK:-${APP_ROOT}/current}"
VENV_DIR="${VENV_DIR:-${APP_ROOT}/venv}"
SERVICE_NAME="${SERVICE_NAME:-astrogeo-http.service}"
SERVICE_FILE="${SERVICE_FILE:-/etc/systemd/system/${SERVICE_NAME}}"
SERVICE_TEMPLATE="${SERVICE_TEMPLATE:-deploy/astrogeo-http.service}"
RUNTIME_DIR="${RUNTIME_DIR:-/var/lib/astrogeo}"
LOG_DIR="${LOG_DIR:-/var/log/astrogeo}"
SERVICE_USER="${SERVICE_USER:-astrogeo}"
SERVICE_GROUP="${SERVICE_GROUP:-astrogeo}"
OPS_GROUP="${OPS_GROUP:-astrogeo-ops}"
SMOKE_CITY="${SMOKE_CITY:-Cosenza, Italy}"
SMOKE_DATE="${SMOKE_DATE:-1982-08-25}"
SMOKE_TIME="${SMOKE_TIME:-12:00}"

usage() {
  echo "Usage: sudo $0 /home/ncadmin/astrogeo-release.tar.gz" >&2
}

if [[ $# -ne 1 ]]; then
  usage
  exit 2
fi

BUNDLE="$1"
if [[ ${EUID} -ne 0 ]]; then
  echo "install_remote.sh must run as root via sudo." >&2
  exit 1
fi
if [[ ! -f "${BUNDLE}" ]]; then
  echo "Release bundle not found: ${BUNDLE}" >&2
  exit 1
fi
if ! id "${SERVICE_USER}" >/dev/null 2>&1; then
  echo "Service user does not exist: ${SERVICE_USER}" >&2
  exit 1
fi
if ! getent group "${SERVICE_GROUP}" >/dev/null 2>&1; then
  echo "Service group does not exist: ${SERVICE_GROUP}" >&2
  exit 1
fi

timestamp="$(date -u +%Y%m%d-%H%M%S)"
release_dir="${RELEASES_DIR}/${timestamp}"
previous_current=""
if [[ -L "${CURRENT_LINK}" || -e "${CURRENT_LINK}" ]]; then
  previous_current="$(readlink -f "${CURRENT_LINK}" || true)"
fi
service_backup=""
if [[ -f "${SERVICE_FILE}" ]]; then
  service_backup="$(mktemp /tmp/astrogeo-service.XXXXXX)"
  cp "${SERVICE_FILE}" "${service_backup}"
fi
http_backup=""
if [[ -f "${APP_ROOT}/astrogeo_http.py" ]]; then
  http_backup="$(mktemp /tmp/astrogeo-http.XXXXXX)"
  cp "${APP_ROOT}/astrogeo_http.py" "${http_backup}"
fi

rollback() {
  if [[ -n "${previous_current}" && -d "${previous_current}" ]]; then
    echo "Rolling current symlink back to ${previous_current}" >&2
    ln -sfn "${previous_current}" "${CURRENT_LINK}"
    install -o root -g root -m 0755 "${previous_current}/astrogeo_http.py" "${APP_ROOT}/astrogeo_http.py" || true
  elif [[ -n "${http_backup}" && -f "${http_backup}" ]]; then
    echo "Restoring previous astrogeo_http.py" >&2
    install -o root -g root -m 0755 "${http_backup}" "${APP_ROOT}/astrogeo_http.py" || true
  fi
  if [[ -n "${service_backup}" && -f "${service_backup}" ]]; then
    echo "Restoring previous ${SERVICE_NAME} unit file" >&2
    install -o root -g root -m 0644 "${service_backup}" "${SERVICE_FILE}" || true
    systemctl daemon-reload || true
  fi
}

echo "Installing AstroGeo release ${timestamp}"
mkdir -p "${RELEASES_DIR}" "${release_dir}" "${RUNTIME_DIR}" "${LOG_DIR}"
chown root:root "${APP_ROOT}" "${RELEASES_DIR}" "${release_dir}"
chmod 0755 "${APP_ROOT}" "${RELEASES_DIR}" "${release_dir}"

if getent group "${OPS_GROUP}" >/dev/null 2>&1; then
  chown "${SERVICE_USER}:${OPS_GROUP}" "${RUNTIME_DIR}" "${LOG_DIR}"
  chmod 2770 "${RUNTIME_DIR}" "${LOG_DIR}"
else
  chown "${SERVICE_USER}:${SERVICE_GROUP}" "${RUNTIME_DIR}" "${LOG_DIR}"
  chmod 0750 "${RUNTIME_DIR}" "${LOG_DIR}"
fi

tar -xzf "${BUNDLE}" -C "${release_dir}"

if [[ ! -f "${release_dir}/astrogeo_http.py" ]]; then
  echo "Release is missing astrogeo_http.py" >&2
  exit 1
fi
if [[ ! -f "${release_dir}/src/main.py" ]]; then
  echo "Release is missing src/main.py" >&2
  exit 1
fi
if [[ ! -f "${release_dir}/pyproject.toml" ]]; then
  echo "Release is missing pyproject.toml" >&2
  exit 1
fi

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  echo "Creating virtualenv at ${VENV_DIR}"
  python3 -m venv "${VENV_DIR}"
fi

"${VENV_DIR}/bin/python" -m pip install --upgrade pip
"${VENV_DIR}/bin/python" -m pip install -e "${release_dir}"
"${VENV_DIR}/bin/python" -m pip check

ln -sfn "${release_dir}" "${CURRENT_LINK}"
install -o root -g root -m 0755 "${release_dir}/astrogeo_http.py" "${APP_ROOT}/astrogeo_http.py"

if [[ -f "${release_dir}/${SERVICE_TEMPLATE}" ]]; then
  install -o root -g root -m 0644 "${release_dir}/${SERVICE_TEMPLATE}" "${SERVICE_FILE}"
else
  cat >"${SERVICE_FILE}" <<'UNIT'
[Unit]
Description=AstroGeo thin HTTP wrapper (subprocess to backend CLI)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=astrogeo
Group=astrogeo
WorkingDirectory=/var/lib/astrogeo
Environment=HOME=/var/lib/astrogeo
ExecStart=/opt/astrogeo/venv/bin/python /opt/astrogeo/astrogeo_http.py --host 127.0.0.1 --port 8008 --venv-python /opt/astrogeo/venv/bin/python --main-py /opt/astrogeo/current/src/main.py
Restart=on-failure
RestartSec=2

# Hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/astrogeo /var/log/astrogeo
LockPersonality=true

[Install]
WantedBy=multi-user.target
UNIT
fi

echo "Running CLI smoke test"
if ! sudo -u "${SERVICE_USER}" env HOME="${RUNTIME_DIR}" "${VENV_DIR}/bin/python" \
  "${CURRENT_LINK}/src/main.py" \
  --city "${SMOKE_CITY}" \
  --date "${SMOKE_DATE}" \
  --time "${SMOKE_TIME}" >/tmp/astrogeo-smoke.json; then
  echo "CLI smoke test failed." >&2
  rollback
  exit 1
fi

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}" >/dev/null
if ! systemctl restart "${SERVICE_NAME}"; then
  echo "Service restart failed." >&2
  rollback
  systemctl restart "${SERVICE_NAME}" || true
  exit 1
fi

for _ in 1 2 3 4 5; do
  if curl -fsS http://127.0.0.1:8008/healthz >/dev/null 2>&1; then
    echo "AstroGeo deployed successfully: ${release_dir}"
    [[ -n "${service_backup}" ]] && rm -f "${service_backup}"
    [[ -n "${http_backup}" ]] && rm -f "${http_backup}"
    exit 0
  fi
  sleep 1
done

echo "Health check failed after restart." >&2
journalctl -u "${SERVICE_NAME}" -n 60 --no-pager >&2 || true
rollback
systemctl restart "${SERVICE_NAME}" || true
exit 1
