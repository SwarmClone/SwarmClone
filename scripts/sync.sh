#!/bin/bash

# ==================================================
# 项目依赖同步脚本 | Project Dependencies Sync Script
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
}

# 加载环境信息
load_environment() {
    if [[ ! -f /etc/swarmclone_venv_path ]]; then
        log_error "Virtual environment info not found" "未找到虚拟环境信息"
        log_error "Please run ckenv.sh first" "请先运行ckenv.sh"
        exit 1
    fi
    
    VENV_PATH=$(cat /etc/swarmclone_venv_path)
    
    if [[ ! -f "$VENV_PATH/bin/activate" ]]; then
        log_error "Invalid virtual environment: $VENV_PATH" "虚拟环境无效: $VENV_PATH"
        exit 1
    fi
    
    source "$VENV_PATH/bin/activate"
    
    if [[ -z "${VIRTUAL_ENV:-}" ]]; then
        log_error "Failed to activate virtual environment" "虚拟环境激活失败"
        exit 1
    fi
    
    log_info "Virtual environment activated: $VIRTUAL_ENV" "虚拟环境已激活: $VIRTUAL_ENV"
}

# 验证uv安装
check_uv() {
    if ! command -v uv >/dev/null; then
        log_error "uv command not found" "未找到uv命令"
        log_error "Please run ibpyd.sh first" "请先运行ibpyd.sh"
        exit 1
    fi
    
    log_info "uv version: $(uv --version)" "uv版本: $(uv --version)"
}

# 同步依赖
sync_dependencies() {
    local max_retries=3
    local retry_count=0
    
    while (( retry_count < max_retries )); do
        log_info "Syncing dependencies (attempt $((retry_count+1))/$max_retries)..." 
                "同步依赖 (尝试 $((retry_count+1))/$max_retries)..."
        
        if uv sync --group linux --active --no-build-isolation; then
            log_info "Dependencies synced successfully" "依赖同步成功"
            return 0
        fi
        
        retry_count=$((retry_count+1))
        log_warn "Dependency sync failed, cleaning cache and retrying..." 
                 "依赖同步失败，清理缓存后重试..."
        uv clean
        sleep 5
    done
    
    log_error "Dependency sync failed after $max_retries attempts" 
             "依赖同步失败，尝试 $max_retries 次后仍失败"
    return 1
}

# 主函数 | Main function
main() {
    check_root
    load_environment
    check_uv
    sync_dependencies
    
    log_info "${GREEN}=== Project dependencies synced successfully ===" 
             "=== 项目依赖同步完成 ==="
    log_info "Project is ready to use!${NC}" "项目已准备好，可以开始使用!${NC}"
}

main "$@"