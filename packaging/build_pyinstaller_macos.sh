#!/usr/bin/env bash
# Build Hoops Mac PyInstaller onedir (API + bridge + supervisor), stage, zip.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VENV="${ROOT}/packaging/.venv"
PYTHON="${VENV}/bin/python"
PIP="${VENV}/bin/pip"

if [[ ! -x "${PYTHON}" ]]; then
  echo "==> Creating packaging/.venv"
  python3 -m venv "${VENV}"
fi

echo "==> Installing freeze deps + api requirements"
"${PIP}" install -q -U pip wheel
"${PIP}" install -q pyinstaller
"${PIP}" install -q -r api/requirements.txt

# Ensure UI exists before stage
if [[ ! -f frontend/dist/index.html ]]; then
  (cd frontend && npm ci && npm run build)
fi

export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"

COMMON_ARGS=(
  --noconfirm
  --clean
  --onedir
  --paths "${ROOT}"
  --paths "${ROOT}/games"
  --hidden-import=uvicorn.logging
  --hidden-import=uvicorn.loops
  --hidden-import=uvicorn.loops.auto
  --hidden-import=uvicorn.protocols
  --hidden-import=uvicorn.protocols.http
  --hidden-import=uvicorn.protocols.http.auto
  --hidden-import=uvicorn.protocols.websockets
  --hidden-import=uvicorn.protocols.websockets.auto
  --hidden-import=uvicorn.lifespan
  --hidden-import=uvicorn.lifespan.on
  --hidden-import=api
  --hidden-import=api.main
  --hidden-import=api.config
  --hidden-import=api.game_manager
  --hidden-import=api.database
  --hidden-import=api.audio_manager
  --hidden-import=api.models
  --hidden-import=api.level_scaling
  --hidden-import=api.runtime_paths
  --hidden-import=hardware_config
  --hidden-import=ws_bridge
  --hidden-import=game_play
  --hidden-import=game_play.Play
  --hidden-import=game_play.game_running
  --hidden-import=led
  --hidden-import=led.led_control
  --hidden-import=model
  --hidden-import=model.setting
  --hidden-import=model.game
  --hidden-import=model.group
  --collect-all=fastapi
  --collect-all=uvicorn
  --collect-all=starlette
  --collect-all=pydantic
  --collect-all=httpx
  --collect-all=anyio
  --collect-all=serial
  --collect-submodules=game_play
  --collect-submodules=led
  --collect-submodules=model
  --collect-submodules=model_in
  --collect-submodules=audio_play
  --collect-submodules=database
  --collect-submodules=util
  --collect-submodules=net
)

# pygame optional at runtime; collect if installed
if "${PYTHON}" -c "import pygame" 2>/dev/null; then
  COMMON_ARGS+=(--collect-all=pygame)
fi

echo "==> PyInstaller hoops-api"
"${PYTHON}" -m PyInstaller "${COMMON_ARGS[@]}" \
  --name hoops-api \
  --distpath "${ROOT}/dist/pyinstaller" \
  packaging/run_api.py

echo "==> PyInstaller hoops-bridge"
"${PYTHON}" -m PyInstaller "${COMMON_ARGS[@]}" \
  --name hoops-bridge \
  --distpath "${ROOT}/dist/pyinstaller" \
  packaging/run_bridge.py

echo "==> PyInstaller LED-Hoops (supervisor)"
"${PYTHON}" -m PyInstaller \
  --noconfirm --clean --onedir --paths "${ROOT}" \
  --name LED-Hoops \
  --distpath "${ROOT}/dist/pyinstaller" \
  --hidden-import=api.runtime_paths \
  packaging/supervisor.py

echo "==> Staging allowlist"
bash packaging/stage_release.sh
STAGE="$(cat dist/release/.last_stage_macos)"

echo "==> Copying onedir trees into stage"
rm -rf "${STAGE}/hoops-api" "${STAGE}/hoops-bridge" "${STAGE}/LED-Hoops"
cp -R "${ROOT}/dist/pyinstaller/hoops-api" "${STAGE}/hoops-api"
cp -R "${ROOT}/dist/pyinstaller/hoops-bridge" "${STAGE}/hoops-bridge"
cp -R "${ROOT}/dist/pyinstaller/LED-Hoops" "${STAGE}/LED-Hoops"

# Re-assert no .py leaked into stage (PyInstaller should not ship .py)
PY_HITS="$(find "${STAGE}" -name '*.py' -print 2>/dev/null || true)"
if [[ -n "${PY_HITS}" ]]; then
  echo "ERROR: .py found after binary copy:"
  echo "${PY_HITS}"
  exit 1
fi

ZIP_NAME="$(basename "${STAGE}")-pyinstaller.zip"
mkdir -p "${ROOT}/dist/release"
(
  cd "${ROOT}/dist/release"
  rm -f "${ZIP_NAME}"
  zip -qy -r "${ZIP_NAME}" "$(basename "${STAGE}")"
)
echo "==> Wrote dist/release/${ZIP_NAME}"
echo "Smoke: cd ${STAGE} && ./LED-Hoops/LED-Hoops"
