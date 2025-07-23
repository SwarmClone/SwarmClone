#!/bin/bash

# ==================================================
# 系统环境设置脚本 | System Environment Setup Script
# 要求必须以root权限运行 | Must run with root privileges
# ==================================================

set -euo pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 日志函数
log_info() { 
    echo -e "${GREEN}[INFO] $1${NC}"
}

log_warn() { 
    echo -e "${YELLOW}[WARN] $1${NC}"
}

log_error() { 
    echo -e "${RED}[ERROR] $1${NC}"
}

# 检查root权限
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root" "此脚本必须以root权限运行"
        log_error "Please use: sudo $0" "请使用: sudo $0"
        exit 1
    fi
    log_info "✓ Running with root privileges" "✓ 以root权限运行"
}

# 获取系统Python
get_system_python() {
    # 查找Python解释器
    local candidates=()
    
    for version in 3.12 3.11 3.10; do
        for bin in /usr/bin/python$version /usr/local/bin/python$version; do
            if [[ -x "$bin" ]]; then
                candidates+=("$bin")
            fi
        done
    done
    
    if [[ -x "/usr/bin/python3" ]]; then
        candidates+=("/usr/bin/python3")
    fi
    
    if [[ ${#candidates[@]} -gt 0 ]]; then
        echo "${candidates[-1]}"
        return 0
    fi
    
    log_error "Python interpreter not found" "未找到Python解释器"
    return 1
}

# 验证Python版本
validate_python_version() {
    local python_exec=$1
    local version
    
    version=$("$python_exec" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null) || {
        log_error "Failed to get Python version from: $python_exec" "无法从 $python_exec 获取Python版本"
        return 1
    }
    
    if [[ "$version" =~ ^3\.(1[0-9]|2[0-9]) ]]; then
        log_info "Python version meets requirement: $version" "Python版本满足要求: $version"
        return 0
    else
        log_error "Python version too low ($version < 3.10)" "Python版本过低 ($version < 3.10)"
        return 1
    fi
}

# 安装Python
install_python() {
    log_info "Installing Python 3.10+" "正在安装Python 3.10+"
    
    # Ubuntu/Debian
    if command -v apt-get >/dev/null; then
        add-apt-repository -y ppa:deadsnakes/ppa
        apt-get update
        apt-get install -y python3.10 python3.10-dev python3.10-venv
        ln -sf /usr/bin/python3.10 /usr/local/bin/python
        ln -sf /usr/bin/python3.10 /usr/local/bin/python3
        return 0
    fi
    
    # CentOS/RHEL
    if command -v yum >/dev/null; then
        yum install -y gcc openssl-devel bzip2-devel libffi-devel zlib-devel
        curl -O https://www.python.org/ftp/python/3.10.13/Python-3.10.13.tgz
        tar xzf Python-3.10.13.tgz
        cd Python-3.10.13
        ./configure --enable-optimizations
        make altinstall
        ln -sf /usr/local/bin/python3.10 /usr/bin/python
        cd ..
        rm -rf Python-3.10.13*
        return 0
    fi
    
    log_error "Unsupported Linux distribution" "不支持的Linux发行版"
    return 1
}

# 安装CMake
install_cmake() {
    local required_version="3.26"
    
    # 检查现有版本
    if command -v cmake >/dev/null; then
        local current_version=$(cmake --version | head -n1 | awk '{print $3}')
        if printf '%s\n%s\n' "$required_version" "$current_version" | sort -V -C; then
            log_info "CMake version meets requirement ($current_version)" "CMake版本满足要求 ($current_version)"
            return 0
        fi
    fi
    
    log_info "Installing CMake ≥ $required_version" "正在安装CMake ≥ $required_version"
    
    # Ubuntu/Debian
    if command -v apt-get >/dev/null; then
        wget -O - https://apt.kitware.com/keys/kitware-archive-latest.asc 2>/dev/null | \
            gpg --dearmor -o /usr/share/keyrings/kitware-archive-keyring.gpg
        echo "deb [signed-by=/usr/share/keyrings/kitware-archive-keyring.gpg] https://apt.kitware.com/ubuntu/ $(lsb_release -cs) main" | \
            tee /etc/apt/sources.list.d/kitware.list >/dev/null
        apt-get update
        apt-get install -y cmake cmake-curses-gui
        return 0
    fi
    
    # CentOS/RHEL
    if command -v yum >/dev/null; then
        yum install -y epel-release
        yum install -y cmake3
        ln -sf /usr/bin/cmake3 /usr/bin/cmake
        return 0
    fi
    
    log_error "Failed to install CMake" "无法安装CMake"
    return 1
}

# 安装系统依赖
install_system_deps() {
    log_info "Installing system dependencies" "正在安装系统依赖"
    
    # Ubuntu/Debian
    if command -v apt-get >/dev/null; then
        apt-get update
        apt-get install -y \
            build-essential \
            python3-pip \
            python3-virtualenv \
            libgl1-mesa-dev \
            libglu1-mesa-dev \
            freeglut3-dev \
            python3-dev \
            software-properties-common \
            lsb-release \
            curl \
            wget \
            git
        return 0
    fi
    
    # CentOS/RHEL
    if command -v yum >/dev/null; then
        yum groupinstall -y "Development Tools"
        yum install -y \
            mesa-libGL-devel \
            mesa-libGLU-devel \
            freeglut-devel \
            python3-devel \
            curl \
            wget \
            git
        return 0
    fi
    
    log_error "Unsupported Linux distribution" "不支持的Linux发行版"
    return 1
}

# 创建虚拟环境
create_virtualenv() {
    local python_exec=$1
    local venv_dir="/opt/swarmclone_venv"
    
    log_info "Creating virtual environment: $venv_dir" "创建虚拟环境: $venv_dir"
    
    # 确保目录存在
    mkdir -p "$venv_dir"
    chmod 755 "$venv_dir"
    
    # 创建虚拟环境
    "$python_exec" -m venv "$venv_dir" || {
        log_error "Failed to create virtual environment" "创建虚拟环境失败"
        return 1
    }
    
    # 记录环境信息
    echo "$venv_dir" > /etc/swarmclone_venv_path
    echo "$python_exec" > /etc/swarmclone_python_path
    
    log_info "Virtual environment created successfully" "虚拟环境创建成功"
}

# 主函数
main() {
    check_root
    
    log_info "=== Starting environment setup ===" "=== 开始环境设置 ==="
    
    # 获取系统Python
    PYTHON_EXEC=$(get_system_python) || {
        log_error "Python interpreter not found" "未找到Python解释器"
        install_python || exit 1
        PYTHON_EXEC="/usr/local/bin/python" # 新安装的Python路径
        validate_python_version "$PYTHON_EXEC" || {
            log_error "Python version still not satisfied" "Python版本仍不满足要求"
            exit 1
        }
    }
    
    # 验证版本
    validate_python_version "$PYTHON_EXEC" || {
        log_warn "System Python version too low" "系统Python版本过低"
        install_python || exit 1
        PYTHON_EXEC="/usr/local/bin/python"
        validate_python_version "$PYTHON_EXEC" || {
            log_error "Python version still not satisfied" "Python版本仍不满足要求"
            exit 1
        }
    }
    
    # 安装系统依赖
    install_system_deps || exit 1
    
    # 安装CMake
    install_cmake || exit 1
    
    # 创建虚拟环境
    create_virtualenv "$PYTHON_EXEC" || exit 1
    
    log_info "${GREEN}=== Environment setup completed ===" "=== 环境设置完成 ==="
    log_info "Virtual environment path: $(cat /etc/swarmclone_venv_path)" "虚拟环境路径: $(cat /etc/swarmclone_venv_path)"
    log_info "Python path: $(cat /etc/swarmclone_python_path)${NC}" "Python路径: $(cat /etc/swarmclone_python_path)${NC}"
}

main "$@"