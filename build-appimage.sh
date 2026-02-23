#!/usr/bin/env bash
set -euo pipefail

APP_NAME="QuantumHub"
APP_VERSION="0.3.0"
ARCH="x86_64"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build"
DIST_DIR="${SCRIPT_DIR}/dist"
APPDIR="${BUILD_DIR}/${APP_NAME}.AppDir"
APPIMAGE_NAME="${APP_NAME}-${APP_VERSION}-${ARCH}.AppImage"
VENV_DIR="${SCRIPT_DIR}/.venv"

echo "=== Building ${APP_NAME} ${APP_VERSION} AppImage ==="

# ── 1. Check dependencies ────────────────────────────────
echo ""
echo "[1/5] Checking dependencies..."

# Use project venv if available, otherwise system python
if [ -f "${VENV_DIR}/bin/python3" ]; then
    PYTHON="${VENV_DIR}/bin/python3"
    PIP="${VENV_DIR}/bin/pip"
    echo "  Using venv: ${VENV_DIR}"
else
    PYTHON="python3"
    PIP="pip3"
fi

if ! "${PYTHON}" --version &>/dev/null; then
    echo "ERROR: python3 not found"
    exit 1
fi

# Install PyInstaller if missing
if ! "${PYTHON}" -m PyInstaller --version &>/dev/null; then
    echo "  Installing PyInstaller..."
    "${PIP}" install pyinstaller
fi

echo "  Python: $("${PYTHON}" --version)"
echo "  PyInstaller: $("${PYTHON}" -m PyInstaller --version)"

# ── 2. PyInstaller build ─────────────────────────────────
echo ""
echo "[2/5] Running PyInstaller..."

cd "${SCRIPT_DIR}"
"${PYTHON}" -m PyInstaller quantumhub.spec --noconfirm

if [ ! -d "${DIST_DIR}/quantumhub" ]; then
    echo "ERROR: PyInstaller output not found at ${DIST_DIR}/quantumhub"
    exit 1
fi

echo "  PyInstaller build complete."

# ── 3. Create AppDir structure ────────────────────────────
echo ""
echo "[3/5] Creating AppDir..."

rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/bin"
mkdir -p "${APPDIR}/usr/share/applications"
mkdir -p "${APPDIR}/usr/share/icons/hicolor/256x256/apps"

# Copy PyInstaller output
cp -r "${DIST_DIR}/quantumhub/"* "${APPDIR}/usr/bin/"

# Desktop file
cp "${SCRIPT_DIR}/quantumhub.desktop" "${APPDIR}/"
cp "${SCRIPT_DIR}/quantumhub.desktop" "${APPDIR}/usr/share/applications/"

# Icon
cp "${SCRIPT_DIR}/quantumhub.png" "${APPDIR}/"
cp "${SCRIPT_DIR}/quantumhub.png" "${APPDIR}/usr/share/icons/hicolor/256x256/apps/"

# AppRun
cat > "${APPDIR}/AppRun" << 'APPRUN'
#!/usr/bin/env bash
SELF="$(readlink -f "$0")"
HERE="${SELF%/*}"
export PATH="${HERE}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/bin:${LD_LIBRARY_PATH:-}"
exec "${HERE}/usr/bin/quantumhub" "$@"
APPRUN
chmod +x "${APPDIR}/AppRun"

echo "  AppDir created at ${APPDIR}"

# ── 4. Download appimagetool ─────────────────────────────
echo ""
echo "[4/5] Preparing appimagetool..."

APPIMAGETOOL="${BUILD_DIR}/appimagetool-${ARCH}.AppImage"

if [ ! -f "${APPIMAGETOOL}" ]; then
    echo "  Downloading appimagetool..."
    curl -L -o "${APPIMAGETOOL}" \
        "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${ARCH}.AppImage"
    chmod +x "${APPIMAGETOOL}"
fi

echo "  appimagetool ready."

# ── 5. Build AppImage ────────────────────────────────────
echo ""
echo "[5/5] Building AppImage..."

cd "${BUILD_DIR}"
ARCH="${ARCH}" "${APPIMAGETOOL}" --no-appstream "${APPDIR}" "${DIST_DIR}/${APPIMAGE_NAME}"

echo ""
echo "=== Done! ==="
echo "AppImage: ${DIST_DIR}/${APPIMAGE_NAME}"
echo ""
echo "Run with:"
echo "  chmod +x ${DIST_DIR}/${APPIMAGE_NAME}"
echo "  ./${DIST_DIR}/${APPIMAGE_NAME}"
