#!/usr/bin/env bash
# 支持 / Supported distros：Debian, Ubuntu, Fedora, CentOS 7/8, Rocky, Alma, openSUSE, Arch

set -euo pipefail

# ---------- 常量 / Constants ----------
VENV_DIR="${HOME}/dev-venv"                       # 虚拟环境目录 / Virtual environment directory
VENV_INFO_FILE="/etc/swarmclone_venv_path"        # 虚拟环境信息文件路径 / Virtual environment info file path

# ---------- 日志 / Logging ----------
log()   { printf '\033[1;34m[INFO]\033[0m %s\n' "$*"; }      # 信息日志 / Info log
warn()  { printf '\033[1;33m[WARN]\033[0m %s\n' "$*"; }      # 警告日志 / Warning log
abort() { printf '\033[1;31m[ERROR]\033[0m %s\n' "$*"; exit 1; } # 错误日志并退出 / Error log and exit

# ---------- 检查root权限 / Check root ----------
check_root() {
    if [[ $EUID -ne 0 ]]; then
        abort "此脚本必须以root权限运行 / This script must be run as root. Please use: sudo $0"
    fi
}

# ---------- 检测发行版 / Detect distro ----------
detect_distro() {
    if [[ -f /etc/os-release ]]; then
        # 加载系统信息 / Load system info
        # shellcheck source=/dev/null
        source /etc/os-release
        DISTRO_ID="${ID:-unknown}"                # 发行版ID / Distro ID
        DISTRO_VER="${VERSION_ID:-unknown}"        # 发行版版本 / Distro version
    else
        abort "无法识别系统 / Cannot identify OS."
    fi

    # 根据发行版确定包管理器 / Determine package manager by distro
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
}

# ---------- 安装包 / Install packages ----------
install_pkg() {
    case "$PKG_MGR" in
        apt)
            log "更新APT包索引 / Updating APT package index..."
            sudo apt-get update -y
            log "安装包 / Installing packages: $*"
            sudo apt-get install -y --no-install-recommends "$@"
            ;;
        dnf)
            log "安装包 / Installing packages: $*"
            sudo dnf install -y "$@"
            ;;
        yum)
            log "安装包 / Installing packages: $*"
            sudo yum install -y "$@"
            ;;
        zypper)
            log "安装包 / Installing packages: $*"
            sudo zypper --non-interactive install "$@"
            ;;
        pacman)
            log "安装包 / Installing packages: $*"
            sudo pacman -Sy --noconfirm "$@"
            ;;
    esac
}

# ---------- 安装CMake / Install CMake ----------
install_cmake() {
    local MIN_CMAKE_VERSION="3.26"  # 最低要求的CMake版本 / Minimum required CMake version
    
    case "$PKG_MGR" in
        apt)
            log "从官方仓库安装CMake / Installing cmake from official repository..."
            install_pkg cmake cmake-curses-gui
            ;;
        dnf)
            install_pkg cmake
            ;;
        yum)
            # CentOS 7需要EPEL仓库 / CentOS 7 requires EPEL repo
            [[ "$DISTRO_VER" =~ ^7 ]] && sudo yum install -y epel-release
            install_pkg cmake
            ;;
        zypper)
            install_pkg cmake
            ;;
        pacman)
            install_pkg cmake
            ;;
    esac
    
    # 验证安装 / Verify installation
    if ! command -v cmake &>/dev/null; then
        abort "CMake安装失败 / CMake installation failed"
    fi
    
    # 检查版本 / Check version
    local cmake_version
    cmake_version=$(cmake --version | head -n1 | awk '{print $3}')
    log "已安装CMake版本 / Installed CMake version: $cmake_version"
    
    # 版本比较 / Version comparison
    if [[ "$(printf '%s\n' "$MIN_CMAKE_VERSION" "$cmake_version" | sort -V | head -n1)" != "$MIN_CMAKE_VERSION" ]]; then
        warn "安装的CMake版本 ($cmake_version) 低于最低要求 ($MIN_CMAKE_VERSION) / Installed CMake version is below minimum required"
        
        # 提供手动安装选项 / Offer manual installation option
        read -rp "是否要手动安装最新CMake? (y/n) / Do you want to install the latest CMake manually? (y/n) " choice
        case "$choice" in
            y|Y)
                log "开始手动安装CMake / Starting manual CMake installation..."
                install_cmake_manual
                return
                ;;
            *)
                warn "继续使用旧版本CMake / Continuing with older CMake version. Some features may not work properly."
                ;;
        esac
    fi
}

# ---------- 手动安装CMake / Manual CMake installation ----------
install_cmake_manual() {
    local INSTALL_DIR="/usr/local"
    local CMAKE_VERSION="3.28.3"  # 最新稳定版 / Latest stable as of 2024
    local CMAKE_URL="https://github.com/Kitware/CMake/releases/download/v${CMAKE_VERSION}/cmake-${CMAKE_VERSION}-linux-x86_64.tar.gz"
    local TEMP_DIR=$(mktemp -d)
    
    log "从官方发布下载CMake ${CMAKE_VERSION} / Downloading CMake from official release..."
    curl -fsSL "$CMAKE_URL" -o "$TEMP_DIR/cmake.tar.gz"
    
    log "解压CMake / Extracting CMake..."
    tar -xzf "$TEMP_DIR/cmake.tar.gz" -C "$TEMP_DIR"
    
    log "安装到 ${INSTALL_DIR} / Installing to ${INSTALL_DIR}..."
    sudo cp -r "$TEMP_DIR/cmake-${CMAKE_VERSION}-linux-x86_64/"* "$INSTALL_DIR"
    
    # 清理临时文件 / Clean up
    rm -rf "$TEMP_DIR"
    
    # 验证新安装 / Verify new installation
    local new_version=$(cmake --version | head -n1 | awk '{print $3}')
    if [[ "$(printf '%s\n' "$MIN_CMAKE_VERSION" "$new_version" | sort -V | head -n1)" != "$MIN_CMAKE_VERSION" ]]; then
        abort "手动CMake安装失败 / Manual CMake installation failed"
    fi
    
    log "成功安装CMake ${new_version} / Successfully installed CMake ${new_version}"
}

# ---------- 设置虚拟环境 / Setup virtualenv ----------
setup_venv() {
    log "在 $VENV_DIR 设置虚拟环境 / Setting up virtualenv at $VENV_DIR..."
    
    # 安装Python（如果不存在） / Install Python if not available
    if ! command -v python3 >/dev/null; then
        log "未找到Python，正在安装 / Python not found, installing..."
        install_pkg python3 python3-venv python3-pip
    fi

    # 创建虚拟环境（如果不存在） / Create venv if not exists
    if [[ ! -d "$VENV_DIR" ]]; then
        log "创建虚拟环境 / Creating virtual environment..."
        python3 -m venv "$VENV_DIR"
    fi

    # 激活虚拟环境 / Activate venv
    # shellcheck source=/dev/null
    source "$VENV_DIR/bin/activate"

    # 确保pip存在 / Ensure pip exists
    if ! command -v pip >/dev/null; then
        log "虚拟环境中未找到pip，正在手动安装 / Pip not found in virtual environment, installing manually..."
        curl -sSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
        python /tmp/get-pip.py
        rm /tmp/get-pip.py
    fi

    # 升级pip并安装uv / Upgrade pip and install uv
    log "升级pip / Upgrading pip..."
    python -m pip install --upgrade pip
    log "安装uv / Installing uv..."
    python -m pip install uv

    # 记录虚拟环境路径 / Record venv path
    echo "$VENV_DIR" | sudo tee "$VENV_INFO_FILE" >/dev/null
    log "虚拟环境信息已保存到 $VENV_INFO_FILE / Virtualenv info saved to $VENV_INFO_FILE"
}

# ---------- 安装Python依赖 / Install Python dependencies ----------
install_python_deps() {
    log "在虚拟环境中安装Python依赖 / Installing Python dependencies in virtualenv..."
    UV_TORCH_BACKEND=auto python -m uv pip install torch torchaudio
}

# ---------- 主函数 / Main ----------
main() {
    check_root
    detect_distro
    
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

    install_cmake
    setup_venv
    install_python_deps

    log "全部完成！ / All done!"
    log "激活虚拟环境：source $VENV_DIR/bin/activate / To activate virtualenv"
    log "同步依赖：sudo scripts/sync.sh / To sync dependencies"
}

main "$@"