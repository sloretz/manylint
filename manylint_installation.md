# `manylint` Installation Design & User Story

`manylint` is distributed as a **single, self-contained static executable** for each major operating system and CPU architecture. Users and CI runners can install and run `manylint` immediately without needing a ROS 2 environment, Python virtualenvs, or system `apt`/`brew` packages.

---

## 1. GitHub Release Artifacts Matrix

Each GitHub Release (`https://github.com/<org>/manylint/releases/tag/vX.Y.Z`) publishes the following standalone binaries alongside an `install.sh` script and a `SHA256SUMS` checksum manifest:

| Asset Filename | Operating System | CPU Architecture (`uname -m`) |
| :--- | :--- | :--- |
| **`manylint-linux-amd64`** | Linux | `x86_64` / `amd64` |
| **`manylint-linux-arm64`** | Linux | `aarch64` / `arm64` |
| **`manylint-osx-arm64`** | macOS (Apple Silicon M1–M4) | `arm64` |
| **`manylint-osx-amd64`** | macOS (Intel) | `x86_64` |
| **`manylint-windows-amd64.exe`** | Windows | `x86_64` / `AMD64` |
| **`SHA256SUMS`** | All | SHA-256 checksums for all release binaries |
| **`install.sh`** | Linux / macOS | Automated user-space installer script |

---

## 2. Quick Install via `curl ... | bash` (Linux & macOS)

### A. Default Installation (Latest Release into `~/.local/bin`)
Users can install `manylint` into their home directory (`~/.local/bin/manylint`) with a single command—no `sudo` or root privileges required:

```bash
curl -fsSL https://github.com/<org>/manylint/releases/latest/download/install.sh | bash
```

### B. Installing a Specific Version or Custom Directory
The installer supports environment variables (or CLI flags via `bash -s --`) for reproducible setups and CI environments:

```bash
# Install a pinned version:
curl -fsSL https://github.com/<org>/manylint/releases/latest/download/install.sh | MANYLINT_VERSION=v0.2.0 bash

# Install to a custom directory:
curl -fsSL https://github.com/<org>/manylint/releases/latest/download/install.sh | MANYLINT_INSTALL_DIR="$HOME/bin" bash
```

---

## 3. How the `install.sh` Script Works

When a user runs `curl ... | bash`, the installer performs six steps:

1. **Detect OS and Architecture**:
   * Uses `uname -s` to map `Linux` $\rightarrow$ `linux` and `Darwin` $\rightarrow$ `osx`.
   * Uses `uname -m` to map `x86_64`/`amd64` $\rightarrow$ `amd64` and `aarch64`/`arm64` $\rightarrow$ `arm64`.
2. **Determine Download URL**:
   * Uses `/releases/latest/download/manylint-<os>-<arch>` by default, or `/releases/download/${MANYLINT_VERSION}/manylint-<os>-<arch>` when `MANYLINT_VERSION` is specified.
3. **Download & Verify Checksum**:
   * Downloads `manylint-<os>-<arch>` and `SHA256SUMS` into a temporary directory (`mktemp -d`) and verifies the binary's integrity with `sha256sum` (Linux) or `shasum -a 256` (macOS).
4. **Install into `~/.local/bin`**:
   * Creates `~/.local/bin` (if it does not already exist), moves the binary to `~/.local/bin/manylint`, and marks it executable (`chmod +x`).
5. **Ensure `~/.local/bin` is on `PATH`**:
   * Checks whether `~/.local/bin` is currently present in `$PATH`.
   * If missing, automatically appends `export PATH="$HOME/.local/bin:$PATH"` to the user's shell configuration file (`~/.bashrc`, `~/.zshrc`, or `~/.profile`) and prints a hint to reload the shell (`source ~/.bashrc`).
6. **Verify Execution**:
   * Runs `~/.local/bin/manylint --version` and prints a confirmation message.

### Reference `install.sh` Implementation

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO="${MANYLINT_REPO:-<org>/manylint}"
VERSION="${MANYLINT_VERSION:-latest}"
INSTALL_DIR="${MANYLINT_INSTALL_DIR:-$HOME/.local/bin}"

# 1. Detect OS
RAW_OS="$(uname -s)"
case "$RAW_OS" in
  Linux*)  OS="linux" ;;
  Darwin*) OS="osx" ;;
  *)
    echo "Error: Unsupported operating system '$RAW_OS'. For Windows, download manylint-windows-amd64.exe." >&2
    exit 1
    ;;
esac

# 2. Detect CPU Architecture
RAW_ARCH="$(uname -m)"
case "$RAW_ARCH" in
  x86_64|amd64)  ARCH="amd64" ;;
  aarch64|arm64) ARCH="arm64" ;;
  *)
    echo "Error: Unsupported architecture '$RAW_ARCH'." >&2
    exit 1
    ;;
esac

ASSET_NAME="manylint-${OS}-${ARCH}"
if [ "$VERSION" = "latest" ]; then
  BASE_URL="https://github.com/${REPO}/releases/latest/download"
else
  BASE_URL="https://github.com/${REPO}/releases/download/${VERSION}"
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "==> Downloading ${ASSET_NAME} (${VERSION})..."
curl -fsSL "${BASE_URL}/${ASSET_NAME}" -o "${TMP_DIR}/${ASSET_NAME}"
curl -fsSL "${BASE_URL}/SHA256SUMS" -o "${TMP_DIR}/SHA256SUMS"

# 3. Verify SHA-256 Checksum
echo "==> Verifying SHA-256 checksum..."
(
  cd "$TMP_DIR"
  if command -v sha256sum >/dev/null 2>&1; then
    grep " ${ASSET_NAME}\$" SHA256SUMS | sha256sum -c -
  elif command -v shasum >/dev/null 2>&1; then
    grep " ${ASSET_NAME}\$" SHA256SUMS | shasum -a 256 -c -
  fi
)

# 4. Install Binary into ~/.local/bin
mkdir -p "$INSTALL_DIR"
mv "${TMP_DIR}/${ASSET_NAME}" "${INSTALL_DIR}/manylint"
chmod +x "${INSTALL_DIR}/manylint"

echo "==> Installed manylint to ${INSTALL_DIR}/manylint"

# 5. Ensure INSTALL_DIR is on PATH
case ":$PATH:" in
  *":${INSTALL_DIR}:"*)
    ;;
  *)
    SHELL_NAME="$(basename "${SHELL:-bash}")"
    case "$SHELL_NAME" in
      zsh)  RC_FILE="$HOME/.zshrc" ;;
      bash) RC_FILE="$HOME/.bashrc" ;;
      *)    RC_FILE="$HOME/.profile" ;;
    esac

    PATH_LINE="export PATH=\"${INSTALL_DIR}:\$PATH\""
    if [ ! -f "$RC_FILE" ] || ! grep -Fq "$INSTALL_DIR" "$RC_FILE"; then
      echo "" >> "$RC_FILE"
      echo "# Added by manylint installer" >> "$RC_FILE"
      echo "$PATH_LINE" >> "$RC_FILE"
      echo "==> Added ${INSTALL_DIR} to PATH in ${RC_FILE}"
    fi
    echo "==> Run 'source ${RC_FILE}' (or open a new terminal) to use 'manylint'."
    ;;
esac

"${INSTALL_DIR}/manylint" --version
```

---

## 4. Direct Manual Download (Linux, macOS, and Windows)

Users who prefer downloading the binary directly without an installer script can grab the executable for their platform from the GitHub Releases page:

### Linux / macOS Direct Download
```bash
mkdir -p ~/.local/bin
curl -fsSL https://github.com/<org>/manylint/releases/latest/download/manylint-linux-amd64 \
  -o ~/.local/bin/manylint
chmod +x ~/.local/bin/manylint
```

### Windows (PowerShell)
```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.local\bin" | Out-Null
Invoke-WebRequest `
  -Uri "https://github.com/<org>/manylint/releases/latest/download/manylint-windows-amd64.exe" `
  -OutFile "$env:USERPROFILE\.local\bin\manylint.exe"
```

---

## 5. Uninstallation

Because `manylint` is a single self-contained binary with no external runtime dependencies in the user's home directory, uninstalling is a single `rm` command:

```bash
rm -f ~/.local/bin/manylint
```
