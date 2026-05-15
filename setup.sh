#!/usr/bin/env bash
# setup.sh — GPU readiness check & NVIDIA Container Toolkit installer
# ─────────────────────────────────────────────────────────────────────────────
# Supports: Linux (x86_64/arm64) with NVIDIA GPU
#           macOS (Apple Silicon — Metal auto-detected, no toolkit needed)
# Skips:    Windows (use WSL2 + Docker Desktop GPU support manually)
#
# Usage: bash setup.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Colour helpers ────────────────────────────────────────────────────────────
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*"; }
header()  { echo -e "\n${BOLD}$*${RESET}"; }

# ── OS detection ──────────────────────────────────────────────────────────────
OS="$(uname -s)"

if [[ "$OS" == "MINGW"* || "$OS" == "CYGWIN"* || "$OS" == "MSYS"* ]]; then
  error "Windows detected. This script does not run on Windows."
  echo   "  → For NVIDIA GPU support on Windows, use Docker Desktop with WSL2"
  echo   "    and follow: https://docs.nvidia.com/cuda/wsl-user-guide/index.html"
  exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
# macOS branch
# ─────────────────────────────────────────────────────────────────────────────
if [[ "$OS" == "Darwin" ]]; then
  header "=== macOS detected ==="

  ARCH="$(uname -m)"

  if [[ "$ARCH" == "arm64" ]]; then
    success "Apple Silicon (${ARCH}) — Ollama Docker image uses Metal GPU automatically."
    echo    "  No NVIDIA Container Toolkit is required or available on macOS."
    echo    "  Metal acceleration is enabled out of the box."
    echo
    info "Run the stack normally:"
    echo "  docker compose up -d"
    echo
    warn "If you notice slow inference, ensure Docker Desktop has sufficient"
    echo "  memory allocated (Settings → Resources → Memory ≥ 8 GB recommended)."
  else
    warn "Intel Mac (${ARCH}) detected — no GPU acceleration is available via Docker."
    echo "  NVIDIA Container Toolkit does not support macOS."
    echo "  Ollama will run on CPU inside the container."
    echo
    info "Run the stack normally (CPU only):"
    echo "  docker compose up -d"
  fi

  exit 0
fi

# ─────────────────────────────────────────────────────────────────────────────
# Linux branch
# ─────────────────────────────────────────────────────────────────────────────
if [[ "$OS" == "Linux" ]]; then
  header "=== Linux detected ==="

  # ── 1. Check for NVIDIA GPU ─────────────────────────────────────────────
  if ! command -v nvidia-smi &>/dev/null; then
    warn "nvidia-smi not found. Checking for NVIDIA PCI device..."
    if lspci 2>/dev/null | grep -qi nvidia; then
      warn "NVIDIA PCI device found but drivers are not installed."
      echo "  Install drivers first: https://www.nvidia.com/Download/index.aspx"
      echo "  Then re-run this script."
    else
      info "No NVIDIA GPU detected. Ollama will run on CPU."
      echo
      info "Run the stack normally (CPU only):"
      echo "  docker compose up -d"
    fi
    exit 0
  fi

  success "NVIDIA GPU found:"
  nvidia-smi --query-gpu=name,driver_version,memory.total \
             --format=csv,noheader 2>/dev/null | \
    while IFS=, read -r name driver mem; do
      echo "    GPU  : ${name}"
      echo "    Driver: ${driver}"
      echo "    VRAM  : ${mem}"
    done
  echo

  # ── 2. Check for NVIDIA Container Toolkit ──────────────────────────────
  header "Checking NVIDIA Container Toolkit..."

  if command -v nvidia-ctk &>/dev/null; then
    success "nvidia-ctk already installed ($(nvidia-ctk --version 2>&1 | head -1))."
    TOOLKIT_INSTALLED=true
  else
    warn "nvidia-ctk not found. Installing NVIDIA Container Toolkit..."
    TOOLKIT_INSTALLED=false
  fi

  if [[ "$TOOLKIT_INSTALLED" == false ]]; then
    # Detect Linux distro
    if [[ -f /etc/os-release ]]; then
      # shellcheck source=/dev/null
      source /etc/os-release
      DISTRO_ID="${ID:-unknown}"
      DISTRO_ID_LIKE="${ID_LIKE:-}"
    else
      DISTRO_ID="unknown"
      DISTRO_ID_LIKE=""
    fi

    info "Detected distro: ${DISTRO_ID}"

    # ── Debian / Ubuntu ────────────────────────────────────────────────
    if [[ "$DISTRO_ID" =~ ^(ubuntu|debian|linuxmint|pop)$ ]] || \
       [[ "$DISTRO_ID_LIKE" =~ debian ]]; then
      info "Installing via apt..."
      # Add NVIDIA GPG key + repo
      curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
        | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

      curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
        | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
        | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list > /dev/null

      sudo apt-get update -qq
      sudo apt-get install -y nvidia-container-toolkit

    # ── RHEL / Fedora / CentOS / Rocky / AlmaLinux ────────────────────
    elif [[ "$DISTRO_ID" =~ ^(rhel|centos|fedora|rocky|almalinux|ol)$ ]] || \
         [[ "$DISTRO_ID_LIKE" =~ rhel|fedora ]]; then
      info "Installing via dnf/yum..."
      curl -s -L https://nvidia.github.io/libnvidia-container/stable/rpm/nvidia-container-toolkit.repo \
        | sudo tee /etc/yum.repos.d/nvidia-container-toolkit.repo > /dev/null

      if command -v dnf &>/dev/null; then
        sudo dnf install -y nvidia-container-toolkit
      else
        sudo yum install -y nvidia-container-toolkit
      fi

    # ── openSUSE / SLES ───────────────────────────────────────────────
    elif [[ "$DISTRO_ID" =~ ^(opensuse|sles)$ ]] || \
         [[ "$DISTRO_ID_LIKE" =~ suse ]]; then
      info "Installing via zypper..."
      sudo zypper ar \
        https://nvidia.github.io/libnvidia-container/stable/rpm/nvidia-container-toolkit.repo
      sudo zypper --gpg-auto-import-keys install -y nvidia-container-toolkit

    else
      error "Unsupported distro: ${DISTRO_ID}. Install manually:"
      echo  "  https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html"
      exit 1
    fi

    success "nvidia-ctk installed: $(nvidia-ctk --version 2>&1 | head -1)"
  fi

  # ── 3. Configure Docker daemon to use nvidia runtime ───────────────────
  header "Configuring Docker to use the NVIDIA runtime..."

  # Check if already configured
  if docker info 2>/dev/null | grep -q "nvidia"; then
    success "Docker runtime already includes 'nvidia'. No changes needed."
  else
    info "Running: nvidia-ctk runtime configure --runtime=docker"
    sudo nvidia-ctk runtime configure --runtime=docker
    info "Restarting Docker daemon..."
    sudo systemctl restart docker
    success "Docker daemon restarted with NVIDIA runtime."
  fi

  # ── 4. Smoke-test ──────────────────────────────────────────────────────
  header "Verifying GPU is accessible inside a container..."

  if docker run --rm --gpus all nvidia/cuda:12.3.1-base-ubuntu22.04 \
       nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null; then
    success "GPU is accessible inside Docker containers."
    GPU_VERIFIED=true
  else
    warn "GPU smoke-test failed. Check that the NVIDIA driver version"
    echo "     is compatible with the installed CUDA toolkit."
    GPU_VERIFIED=false
  fi

  # ── 5. Final instructions ──────────────────────────────────────────────
  echo
  header "=== Setup complete ==="

  if [[ "$GPU_VERIFIED" == true ]]; then
    success "Your system is GPU-ready. Start the full stack with:"
    echo
    echo -e "  ${BOLD}docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d${RESET}"
    echo
    echo "  This passes the GPU override to the Ollama service only."
    echo "  Verify after startup:"
    echo "    docker exec ollama nvidia-smi"
    echo "    docker exec ollama ollama list   # should show llama3.2:3b"
  else
    warn "GPU verification failed. You can still try:"
    echo
    echo "  docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d"
    echo
    echo "  Or fall back to CPU-only:"
    echo "  docker compose up -d"
  fi

  exit 0
fi

# ── Fallback (unknown OS) ──────────────────────────────────────────────────────
error "Unrecognised OS: ${OS}. This script supports Linux and macOS only."
exit 1
