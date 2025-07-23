#!/usr/bin/env bash
# install-dev.sh – 跨发行版一键开发环境
# 支持：Debian, Ubuntu, Fedora, CentOS 7/8, Rocky, Alma, openSUSE, Arch
# Author: <Your Name>

set -euo pipefail

# ---------- 日志 ----------
log()   { printf '\033[1;34m[INFO]\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m[WARN]\033[0m %s\n' "$*"; }
abort() { printf '\033[1;31m[ERROR]\033[0m %s\n' "$*"; exit 1; }

# ---------- 检测发行版 ----------
if [[ -f /etc/os-release ]]; then
    # shellcheck source=/dev/null
    source /etc/os-release
    DISTRO_ID="${ID:-unknown}"               # debian ubuntu fedora ...
    DISTRO_VER="${VERSION_ID:-unknown}"      # 20.04  36     ...
else
    abort "无法识别系统 / Cannot identify OS."
fi

case "$DISTRO_ID" in
    debian|ubuntu)      PKG_MGR="apt" ;;
    fedora)             PKG_MGR="dnf" ;;
    centos|rhel)        [[ "$DISTRO_VER" =~ ^7 ]] && PKG_MGR="yum" || PKG_MGR="dnf" ;;
    rocky|almalinux)    PKG_MGR="dnf" ;;
    opensuse*)          PKG_MGR="zypper" ;;
    arch|manjaro)       PKG_MGR="pacman" ;;
    *) abort "暂不支持该发行版 / Unsupported distro: $DISTRO_ID" ;;
esac

log "检测到发行版 / Detected: $DISTRO_ID $DISTRO_VER ($PKG_MGR)"

# ---------- 通用安装函数 ----------
install_pkg() {
    case "$PKG_MGR" in
        apt)
            sudo apt-get update -y
            sudo apt-get install -y --no-install-recommends "$@"
            ;;
        dnf)
            sudo dnf install -y "$@"
            ;;
        yum)
            sudo yum install -y "$@"
            ;;
        zypper)
            sudo zypper --non-interactive install "$@"
            ;;
        pacman)
            sudo pacman -Sy --noconfirm "$@"
            ;;
    esac
}

# ---------- 安装基础依赖 ----------
log "安装基础开发工具 / Installing base dev tools..."
case "$PKG_MGR" in
    apt)
        install_pkg build-essential ca-certificates curl gpg lsb-release wget \
                    libgl1-mesa-dev libglu1-mesa-dev freeglut3-dev \
                    python3-dev python3-venv python3-pip
        ;;
    dnf|yum)
        install_pkg gcc gcc-c++ make wget curl ca-certificates \
                    mesa-libGL-devel mesa-libGLU-devel freeglut-devel \
                    python3-devel python3-pip
        ;;
    zypper)
        install_pkg gcc gcc-c++ make wget curl ca-certificates \
                    Mesa-libGL-devel Mesa-libGLU-devel freeglut-devel \
                    python3-devel python3-pip
        ;;
    pacman)
        install_pkg base-devel wget curl ca-certificates \
                    mesa glu freeglut \
                    python python-pip
        ;;
esac

# ---------- 安装 CMake ----------
install_cmake() {
    case "$PKG_MGR" in
        apt)
            # Kitware APT 仅支持 Ubuntu 20.04/22.04/24.04 与 Debian 11/12
            if [[ "$DISTRO_ID" == "ubuntu" ]] && [[ "$DISTRO_VER" =~ ^(20.04|22.04|24.04)$ ]]; then
                KEY="/usr/share/keyrings/kitware-archive-keyring.gpg"
                LIST="/etc/apt/sources.list.d/kitware.list"
                if [[ ! -f "$KEY" ]]; then
                    curl -fsSL https://apt.kitware.com/keys/kitware-archive-latest.asc | gpg --dearmor | sudo tee "$KEY" >/dev/null
                fi
                if [[ ! -f "$LIST" ]]; then
                    echo "deb [signed-by=$KEY arch=$(dpkg --print-architecture)] https://apt.kitware.com/ubuntu/ $(lsb_release -cs) main" | sudo tee "$LIST" >/dev/null
                fi
                sudo apt-get update -y
                sudo apt-get install -y cmake cmake-curses-gui
            elif [[ "$DISTRO_ID" == "debian" ]] && [[ "$DISTRO_VER" =~ ^(11|12)$ ]]; then
                KEY="/usr/share/keyrings/kitware-archive-keyring.gpg"
                LIST="/etc/apt/sources.list.d/kitware.list"
                if [[ ! -f "$KEY" ]]; then
                    curl -fsSL https://apt.kitware.com/keys/kitware-archive-latest.asc | gpg --dearmor | sudo tee "$KEY" >/dev/null
                fi
                if [[ ! -f "$LIST" ]]; then
                    echo "deb [signed-by=$KEY] https://apt.kitware.com/debian/ $(lsb_release -cs) main" | sudo tee "$LIST" >/dev/null
                fi
                sudo apt-get update -y
                sudo apt-get install -y cmake cmake-curses-gui
            else
                log "使用发行版自带 cmake / Using distro cmake"
                install_pkg cmake
            fi
            ;;
        dnf)
            # Fedora 官方源 cmake 已足够新
            install_pkg cmake
            ;;
        yum)
            # CentOS 7 可用 epel-release 获取较新 cmake
            [[ "$DISTRO_VER" =~ ^7 ]] && sudo yum install -y epel-release
            install_pkg cmake
            ;;
        zypper|pacman)
            install_pkg cmake
            ;;
    esac
}
install_cmake

# ---------- Python 虚拟环境 ----------
VENV_DIR="${HOME}/dev-venv"
PYTHON_BIN="$VENV_DIR/bin/python"
PIP_BIN="$VENV_DIR/bin/pip"

if [[ ! -d "$VENV_DIR" ]]; then
    log "创建虚拟环境至 $VENV_DIR / Creating venv at $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
fi

log "升级 venv 内 pip / Upgrading pip..."
"$PYTHON_BIN" -m pip install --upgrade pip

# ---------- 安装 PyTorch ----------
log "安装 uv 并安装 PyTorch / Installing uv & PyTorch..."
"$PYTHON_BIN" -m pip install uv
UV_TORCH_BACKEND=auto "$PYTHON_BIN" -m uv pip install torch torchaudio

# ---------- 完成 ----------
log "全部完成！/ All done!"
log "激活虚拟环境：source $VENV_DIR/bin/activate"