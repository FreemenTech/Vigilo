#!/bin/bash
################################################################################
# Vigilo Installation Script
# 
# Automated installation with security hardening for production deployment
#
# Usage:
#   sudo ./install.sh [OPTIONS]
#
# Options:
#   --prefix PATH        Installation directory (default: /opt/vigilo)
#   --user USER          Service user (default: vigilo)
#   --skip-deps          Skip dependency installation
#   --dev                Development mode (no systemd service)
#   --uninstall          Remove Vigilo completely
#   -h, --help           Show this help message
#
# Author: Freemen HOUNGBEDJI
# License: MIT
################################################################################

set -e  # Exit on any error
set -u  # Exit on undefined variable
set -o pipefail  # Exit on pipe failure

################################################################################
# CONFIGURATION
################################################################################

# Default values
INSTALL_PREFIX="/opt/vigilo"
SERVICE_USER="vigilo"
SERVICE_GROUP="vigilo"
SKIP_DEPS=false
DEV_MODE=false
UNINSTALL=false
PYTHON_BIN="/usr/bin/python3"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script metadata
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="1.0.0"

################################################################################
# HELPER FUNCTIONS
################################################################################

print_header() {
    echo -e "${BLUE}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  $1"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ ERROR: $1${NC}" >&2
}

print_warning() {
    echo -e "${YELLOW}⚠️  WARNING: $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

check_os() {
    if [[ ! -f /etc/os-release ]]; then
        print_error "Cannot detect OS (missing /etc/os-release)"
        exit 1
    fi
    
    source /etc/os-release
    
    case "$ID" in
        ubuntu|debian)
            PACKAGE_MANAGER="apt-get"
            ;;
        centos|rhel|fedora)
            PACKAGE_MANAGER="yum"
            ;;
        arch)
            PACKAGE_MANAGER="pacman"
            ;;
        *)
            print_warning "Unsupported OS: $ID (proceeding anyway)"
            PACKAGE_MANAGER="apt-get"
            ;;
    esac
    
    print_success "Detected OS: $PRETTY_NAME"
}

check_dependencies() {
    local missing_deps=()
    
    # Check Python 3
    if ! command -v python3 &> /dev/null; then
        missing_deps+=("python3")
    else
        local python_version=$(python3 --version | awk '{print $2}')
        print_info "Found Python: $python_version"
        
        # Check minimum version (3.8+)
        local major=$(echo "$python_version" | cut -d. -f1)
        local minor=$(echo "$python_version" | cut -d. -f2)
        
        if [[ $major -lt 3 ]] || [[ $major -eq 3 && $minor -lt 8 ]]; then
            print_error "Python 3.8+ required (found $python_version)"
            exit 1
        fi
    fi
    
    # Check pip
    if ! command -v pip3 &> /dev/null; then
        missing_deps+=("python3-pip")
    fi
    
    # Check systemctl (for service mode)
    if [[ "$DEV_MODE" == false ]] && ! command -v systemctl &> /dev/null; then
        print_error "systemd not found (use --dev for development mode)"
        exit 1
    fi
    
    # Report missing dependencies
    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        print_warning "Missing dependencies: ${missing_deps[*]}"
        return 1
    fi
    
    return 0
}

install_system_dependencies() {
    print_header "Installing System Dependencies"
    
    case "$PACKAGE_MANAGER" in
        apt-get)
            apt-get update -qq
            apt-get install -y python3 python3-pip libnotify-bin > /dev/null 2>&1
            ;;
        yum)
            yum install -y python3 python3-pip libnotify > /dev/null 2>&1
            ;;
        pacman)
            pacman -S --noconfirm python python-pip libnotify > /dev/null 2>&1
            ;;
    esac
    
    print_success "System dependencies installed"
}

install_python_dependencies() {
    print_header "Installing Python Dependencies"
    
    if [[ ! -f "$SCRIPT_DIR/requirements.txt" ]]; then
        print_error "requirements.txt not found in $SCRIPT_DIR"
        exit 1
    fi
    
    # Install Python packages
    pip3 install -q -r "$SCRIPT_DIR/requirements.txt" --break-system-packages 2>/dev/null || \
    pip3 install -q -r "$SCRIPT_DIR/requirements.txt"
    
    print_success "Python dependencies installed"
}

create_service_user() {
    print_header "Creating Service User"
    
    # Check if user already exists
    if id "$SERVICE_USER" &>/dev/null; then
        print_info "User '$SERVICE_USER' already exists"
        return 0
    fi
    
    # Create system user
    useradd \
        --system \
        --no-create-home \
        --home-dir "$INSTALL_PREFIX" \
        --shell /bin/false \
        --user-group \
        "$SERVICE_USER"
    
    print_success "Created user: $SERVICE_USER"
}

install_files() {
    print_header "Installing Vigilo Files"
    
    # Create installation directory
    mkdir -p "$INSTALL_PREFIX"
    
    # Copy Python files
    local files_to_copy=(
        "main.py"
        "file_monitoring.py"
        "FileWatcher.py"
        "logger.py"
        "alert_manager.py"
        "command_help.txt"
        "requirements.txt"
        "README.md"
    )
    
    for file in "${files_to_copy[@]}"; do
        if [[ -f "$SCRIPT_DIR/$file" ]]; then
            cp "$SCRIPT_DIR/$file" "$INSTALL_PREFIX/"
            print_info "Copied: $file"
        else
            print_warning "File not found (skipping): $file"
        fi
    done
    
    # Make main.py executable
    chmod +x "$INSTALL_PREFIX/main.py"
    
    # Set ownership
    chown -R "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_PREFIX"
    
    # Set restrictive permissions
    chmod 700 "$INSTALL_PREFIX"
    
    # Create database files with correct permissions
    touch "$INSTALL_PREFIX/file_info.json"
    touch "$INSTALL_PREFIX/file_event.json"
    touch "$INSTALL_PREFIX/alert_history.json"
    
    chmod 600 "$INSTALL_PREFIX"/*.json
    chown "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_PREFIX"/*.json
    
    print_success "Files installed to: $INSTALL_PREFIX"
}

create_symlink() {
    print_header "Creating System Symlink"
    
    # Create symlink in /usr/local/bin
    if [[ -L /usr/local/bin/vigilo ]]; then
        rm /usr/local/bin/vigilo
    fi
    
    ln -s "$INSTALL_PREFIX/main.py" /usr/local/bin/vigilo
    
    print_success "Created symlink: /usr/local/bin/vigilo"
    print_info "You can now run 'vigilo' from anywhere"
}

install_systemd_service() {
    print_header "Installing Systemd Service"
    
    # Create service file
    cat > /etc/systemd/system/vigilo.service << EOF
[Unit]
Description=Vigilo File Integrity Monitoring Service
Documentation=https://github.com/FreemenTech/Vigilo
After=network-online.target
Wants=network-online.target
ConditionPathExists=$INSTALL_PREFIX/main.py

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_GROUP
WorkingDirectory=$INSTALL_PREFIX
ExecStart=$PYTHON_BIN $INSTALL_PREFIX/main.py start
ExecReload=/bin/kill -HUP \$MAINPID

# Restart policy
Restart=on-failure
RestartSec=10
StartLimitInterval=60
StartLimitBurst=3

# Performance
Nice=-5
CPUQuota=20%
MemoryLimit=100M
TasksMax=50

# Security - Filesystem
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$INSTALL_PREFIX
ReadOnlyPaths=/etc /var/log
PrivateTmp=true
NoNewPrivileges=true

# Security - Network
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6

# Security - Capabilities
CapabilityBoundingSet=
AmbientCapabilities=

# Security - System Calls
SystemCallFilter=@system-service
SystemCallFilter=~@privileged @resources
SystemCallErrorNumber=EPERM

# Security - Devices
PrivateDevices=true
DevicePolicy=closed

# Security - Kernel
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectKernelLogs=true
ProtectControlGroups=true

# Security - Misc
RestrictRealtime=true
RestrictSUIDSGID=true
LockPersonality=true
ProtectHostname=true
ProtectClock=true
RemoveIPC=true

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=vigilo

# Environment
Environment="PYTHONUNBUFFERED=1"
Environment="VIGILO_CONFIG=$INSTALL_PREFIX/file_info.json"
Environment="VIGILO_LOG_LEVEL=INFO"

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd
    systemctl daemon-reload
    
    # Enable service
    systemctl enable vigilo.service
    
    print_success "Systemd service installed and enabled"
}

run_security_audit() {
    print_header "Running Security Audit"
    
    # Analyze service security
    local security_score=$(systemd-analyze security vigilo 2>/dev/null | grep "Overall exposure level:" | awk '{print $NF}')
    
    if [[ -n "$security_score" ]]; then
        print_info "Security score: $security_score"
        
        # Show top recommendations
        print_info "Top security recommendations:"
        systemd-analyze security vigilo --no-pager 2>/dev/null | \
            grep -E "UNSAFE|MEDIUM" | \
            head -5 | \
            sed 's/^/  /'
    else
        print_warning "Could not analyze service security (systemd-analyze not available)"
    fi
}

post_install_info() {
    print_header "Installation Complete"
    
    echo ""
    print_success "Vigilo has been successfully installed!"
    echo ""
    
    echo -e "${BLUE}📍 Installation Details:${NC}"
    echo "   • Installation path: $INSTALL_PREFIX"
    echo "   • Service user: $SERVICE_USER"
    echo "   • Command: vigilo"
    echo ""
    
    echo -e "${BLUE}🚀 Quick Start:${NC}"
    echo "   1. Add a file to monitoring:"
    echo "      vigilo add /etc/nginx/nginx.conf --preset full --alert system"
    echo ""
    echo "   2. List monitored files:"
    echo "      vigilo list"
    echo ""
    echo "   3. Start monitoring service:"
    if [[ "$DEV_MODE" == false ]]; then
        echo "      sudo systemctl start vigilo"
        echo "      sudo systemctl status vigilo"
    else
        echo "      vigilo start"
    fi
    echo ""
    
    echo -e "${BLUE}📚 Documentation:${NC}"
    echo "   • Full help: vigilo help"
    echo "   • README: $INSTALL_PREFIX/README.md"
    echo "   • Service logs: journalctl -u vigilo -f"
    echo ""
    
    echo -e "${BLUE}🔒 Security Status:${NC}"
    if [[ "$DEV_MODE" == false ]]; then
        echo "   • Security hardening: ENABLED"
        echo "   • Filesystem isolation: ENABLED"
        echo "   • Syscall filtering: ENABLED"
        echo "   • Run 'systemd-analyze security vigilo' for full audit"
    else
        echo "   • Development mode: Security features disabled"
    fi
    echo ""
    
    print_warning "Remember to configure your files for monitoring before starting!"
}

uninstall() {
    print_header "Uninstalling Vigilo"
    
    # Stop and disable service
    if systemctl is-active --quiet vigilo 2>/dev/null; then
        systemctl stop vigilo
        print_info "Stopped service"
    fi
    
    if systemctl is-enabled --quiet vigilo 2>/dev/null; then
        systemctl disable vigilo
        print_info "Disabled service"
    fi
    
    # Remove service file
    if [[ -f /etc/systemd/system/vigilo.service ]]; then
        rm /etc/systemd/system/vigilo.service
        systemctl daemon-reload
        print_info "Removed service file"
    fi
    
    # Remove symlink
    if [[ -L /usr/local/bin/vigilo ]]; then
        rm /usr/local/bin/vigilo
        print_info "Removed symlink"
    fi
    
    # Ask before removing files
    read -p "Remove installation directory ($INSTALL_PREFIX)? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$INSTALL_PREFIX"
        print_info "Removed installation directory"
    fi
    
    # Ask before removing user
    read -p "Remove service user ($SERVICE_USER)? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        userdel "$SERVICE_USER" 2>/dev/null || true
        print_info "Removed service user"
    fi
    
    print_success "Vigilo has been uninstalled"
}

show_help() {
    cat << EOF
Vigilo Installation Script v$VERSION

USAGE:
    sudo ./install.sh [OPTIONS]

OPTIONS:
    --prefix PATH        Installation directory (default: /opt/vigilo)
    --user USER          Service user (default: vigilo)
    --skip-deps          Skip dependency installation
    --dev                Development mode (no systemd service)
    --uninstall          Remove Vigilo completely
    -h, --help           Show this help message

EXAMPLES:
    # Standard installation
    sudo ./install.sh

    # Custom installation directory
    sudo ./install.sh --prefix /usr/local/vigilo

    # Development mode (no service)
    sudo ./install.sh --dev

    # Uninstall
    sudo ./install.sh --uninstall

REQUIREMENTS:
    • Linux with systemd (Ubuntu, Debian, CentOS, Fedora, Arch)
    • Python 3.8+
    • Root privileges (sudo)

For more information, visit: https://github.com/FreemenTech/Vigilo
EOF
}

################################################################################
# ARGUMENT PARSING
################################################################################

while [[ $# -gt 0 ]]; do
    case $1 in
        --prefix)
            INSTALL_PREFIX="$2"
            shift 2
            ;;
        --user)
            SERVICE_USER="$2"
            SERVICE_GROUP="$2"
            shift 2
            ;;
        --skip-deps)
            SKIP_DEPS=true
            shift
            ;;
        --dev)
            DEV_MODE=true
            shift
            ;;
        --uninstall)
            UNINSTALL=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

################################################################################
# MAIN INSTALLATION FLOW
################################################################################

main() {
    # Show banner
    clear
    print_header "🛡️ VIGILO INSTALLATION v$VERSION"
    
    # Check prerequisites
    check_root
    check_os
    
    # Handle uninstall
    if [[ "$UNINSTALL" == true ]]; then
        uninstall
        exit 0
    fi
    
    # Check dependencies
    if ! check_dependencies; then
        if [[ "$SKIP_DEPS" == false ]]; then
            read -p "Install missing dependencies? [Y/n] " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Nn]$ ]]; then
                install_system_dependencies
            fi
        fi
    fi
    
    # Install Python dependencies
    if [[ "$SKIP_DEPS" == false ]]; then
        install_python_dependencies
    fi
    
    # Create service user (skip in dev mode with existing user)
    if [[ "$DEV_MODE" == false ]]; then
        create_service_user
    fi
    
    # Install files
    install_files
    
    # Create symlink
    create_symlink
    
    # Install systemd service (production mode only)
    if [[ "$DEV_MODE" == false ]]; then
        install_systemd_service
        run_security_audit
    else
        print_warning "Development mode: Systemd service NOT installed"
    fi
    
    # Show post-install info
    post_install_info
}

################################################################################
# ENTRY POINT
################################################################################

# Catch interrupts
trap 'print_error "Installation interrupted"; exit 130' INT TERM

# Run main installation
main

exit 0
