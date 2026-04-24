#!/usr/bin/env bash
set -euo pipefail

REMOTE="${ASTROGEO_REMOTE:-lupoegatta}"
REMOTE_STAGE_DIR="${ASTROGEO_REMOTE_STAGE_DIR:-/home/ncadmin/astrogeo-deploy}"
LOCAL_PYTHON="${LOCAL_PYTHON:-.venv/bin/python}"
SKIP_TESTS="${SKIP_TESTS:-0}"
ALLOW_DIRTY="${ALLOW_DIRTY:-0}"

usage() {
  cat >&2 <<'USAGE'
Usage: deploy/deploy_lupoegatta.sh [--skip-tests] [--allow-dirty]

Environment overrides:
  ASTROGEO_REMOTE            SSH target, default: lupoegatta
  ASTROGEO_REMOTE_STAGE_DIR  Remote staging dir, default: /home/ncadmin/astrogeo-deploy
  LOCAL_PYTHON               Local Python for tests, default: .venv/bin/python
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-tests)
      SKIP_TESTS=1
      shift
      ;;
    --allow-dirty)
      ALLOW_DIRTY=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

repo_root="$(git rev-parse --show-toplevel)"
cd "${repo_root}"

if [[ "${ALLOW_DIRTY}" != "1" ]]; then
  if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "Working tree has tracked changes. Commit them or pass --allow-dirty." >&2
    exit 1
  fi
fi

untracked="$(git ls-files --others --exclude-standard)"
if [[ -n "${untracked}" ]]; then
  echo "Warning: untracked files are not included in the release bundle:" >&2
  echo "${untracked}" >&2
fi

if [[ "${SKIP_TESTS}" != "1" ]]; then
  if [[ ! -x "${LOCAL_PYTHON}" ]]; then
    echo "Local test Python not found or not executable: ${LOCAL_PYTHON}" >&2
    echo "Set LOCAL_PYTHON or pass --skip-tests." >&2
    exit 1
  fi
  "${LOCAL_PYTHON}" -m pytest -q
fi

timestamp="$(date -u +%Y%m%d-%H%M%S)"
bundle="/tmp/astrogeo-release-${timestamp}.tar.gz"
remote_bundle="${REMOTE_STAGE_DIR}/astrogeo-release-${timestamp}.tar.gz"
remote_installer="${REMOTE_STAGE_DIR}/install_remote.sh"

echo "Building release bundle ${bundle}"
git ls-files -z | tar --null -czf "${bundle}" --files-from -

echo "Preparing remote staging directory ${REMOTE}:${REMOTE_STAGE_DIR}"
ssh "${REMOTE}" "mkdir -p '${REMOTE_STAGE_DIR}'"

echo "Uploading release bundle and installer"
scp "${bundle}" "${REMOTE}:${remote_bundle}"
scp deploy/install_remote.sh "${REMOTE}:${remote_installer}"

echo "Running remote installer via sudo"
ssh -tt "${REMOTE}" "chmod +x '${remote_installer}' && sudo '${remote_installer}' '${remote_bundle}'"
