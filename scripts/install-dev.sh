#!/usr/bin/env bash

set -euo pipefail

# ---------- 路径解析 / Path Resolution ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_DIR="${PROJECT_ROOT}/.venv"
PYTHON="${VENV_DIR}/bin/python"
PIP="${VENV_DIR}/bin/pip"

# ---------- 日志 / Logging ----------
log()   { echo -e "\033[1;34m[INFO]\033[0m $*"; }
warn()  { echo -e "\033[1;33m[WARN]\033[0m $*"; }
abort() { echo -e "\033[1;31m[ERROR]\033[0m $*"; exit 1; }

# ---------- 检查root权限 / Check Root ----------
check_root() {
    if [[ $EUID -ne 0 ]]; then
        abort "此脚本必须以root权限运行\nThis script must be run as root. Please use: sudo $0"
    fi
}

# ---------- 系统准备 / System Preparation ----------
prepare_system() {
    # 检测发行版
    if [[ -f /etc/os-release ]]; then
        source /etc/os-release
        DISTRO_ID="${ID:-unknown}"
        DISTRO_VER="${VERSION_ID:-unknown}"
    else
        abort "无法识别系统 / Cannot identify OS."
    fi

    # 安装基础依赖
    case "$DISTRO_ID" in
        debian|ubuntu)
            apt-get update -y
            apt-get install -y --no-install-recommends \
                build-essential python3 python3-venv python3-pip \
                cmake libgl1-mesa-dev libglu1-mesa-dev freeglut3-dev
            ;;
        fedora|centos|rhel|rocky|almalinux)
            [[ "$PKG_MGR" == "yum" && "$DISTRO_VER" =~ ^7 ]] && yum install -y epel-release
            $PKG_MGR install -y \
                gcc gcc-c++ make python3 python3-virtualenv python3-pip \
                cmake mesa-libGL-devel mesa-libGLU-devel freeglut-devel
            ;;
        opensuse*)
            zypper --non-interactive install \
                gcc gcc-c++ make python3 python3-virtualenv python3-pip \
                cmake Mesa-libGL-devel Mesa-libGLU-devel freeglut-devel
            ;;
        arch|manjaro)
            pacman -Sy --noconfirm \
                base-devel python python-pip \
                cmake mesa glu freeglut
            ;;
        *) abort "暂不支持该发行版 / Unsupported distro: $DISTRO_ID" ;;
    esac
}

# ---------- 设置虚拟环境 / Setup Virtualenv ----------
setup_venv() {
    log "设置Python虚拟环境 / Setting up Python virtual environment..."
    
    # 清理旧环境
    [[ -d "$VENV_DIR" ]] && rm -rf "$VENV_DIR"

    # 创建新环境
    python3 -m venv "$VENV_DIR" --clear
    
    # 安装基础工具
    "$PYTHON" -m pip install --upgrade pip setuptools wheel uv
    
    # 安装PyTorch
    UV_TORCH_BACKEND=auto "$PYTHON" -m uv pip install torch torchaudio
    
    log "虚拟环境已创建 / Virtual environment created at $VENV_DIR"
}

# ---------- 主函数 / Main ----------
main() {
    check_root
    prepare_system
    setup_venv

    echo -e "\n\033[1;32m=== 安装完成! ==="
    echo "=== Installation complete! ==="
    echo "请执行以下命令激活环境:"
    echo "Run the following command to activate environment:"
    echo "source ${VENV_DIR}/bin/activate"
}

main "$@"
