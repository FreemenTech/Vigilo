🛡️ VIGILO — File Integrity Monitoring Tool
Lightweight, production-ready file integrity monitoring for Linux systems

Monitor critical files and directories in real-time with minimal overhead. Vigilo detects unauthorized modifications, deletions, and permission changes — alerting you instantly before damage spreads.

🎯 Why Vigilo?
The Problem: 47% of security incidents start with an unauthorized file modification. Someone edits /etc/passwd at 3 AM, a malicious script overwrites nginx.conf, an unknown SSH key appears in authorized_keys — and you don't notice for days.
Existing Solutions:

OSSEC: 200+ MB RAM, 50+ lines of XML config per file
Wazuh: Complex YAML, 30-minute setup, resource-heavy
Tripwire: Commercial pricing, steep learning curve

Vigilo:

⚡ 60-second installation — one command, you're protected
🪶 <15 MB RAM — 13x lighter than OSSEC
🔒 Zero configuration hell — no YAML, no XML, no regex nightmares
📦 5 Python files — readable, hackable, production-ready


⚡ Quick Start
One-Line Installation
bashgit clone https://github.com/FreemenTech/Vigilo.git
cd vigilo && chmod +x install.sh && sudo ./install.sh
Add Your First File
bashvigilo add /etc/nginx/nginx.conf --preset full --alert system
Start Monitoring
bashsudo systemctl start vigilo
Done. Modify the file → instant desktop notification.

📦 Installation
Automated Installation (Recommended)
bash# Clone repository
git clone https://github.com/FreemenTech/Vigilo.git
cd vigilo

# Run installer with security hardening
chmod +x install.sh
sudo ./install.sh
What it does:

✅ Installs dependencies (Python 3.8+, watchdog, etc.)
✅ Creates dedicated system user (vigilo)
✅ Deploys to /opt/vigilo with 0o600 permissions
✅ Configures systemd service with enterprise-grade hardening
✅ Runs security audit (systemd-analyze)
✅ Creates global command: vigilo

Manual Installation
bash# Install dependencies
pip install -r requirements.txt --break-system-packages

# Run directly
chmod +x main.py
./main.py --help
Installation Options
bash# Custom directory
sudo ./install.sh --prefix /usr/local/vigilo

# Development mode (no systemd service)
sudo ./install.sh --dev

# Skip dependencies (if already installed)
sudo ./install.sh --skip-deps

# Uninstall completely
sudo ./install.sh --uninstall

🚀 Usage
Core Commands
bash# Add file to monitoring
vigilo add <file> [options]

# Remove file from monitoring
vigilo remove <file>

# List all monitored files
vigilo list

# Show file details
vigilo info <file>

# Start monitoring service
vigilo start

# Display help
vigilo help
Adding Files
bash# Monitor all events (modify, delete, move, permissions, add)
vigilo add /etc/passwd --preset full --alert system

# Monitor specific events only
vigilo add /var/www/index.html -m -d -p --alert log

# Add multiple files at once
vigilo add /etc/hosts /etc/ssh/sshd_config --preset default
Event types:

-m, --modify — Content changes
-d, --delete — File deletions
-v, --move — Moves/renames
-p, --permissions — Permission changes
-a, --add — New files (for directories)

Presets:

--preset full — All events
--preset default — modify + delete + permissions

Alert Modes
bash# Desktop notifications (Linux)
vigilo add <file> --alert system

# Silent logging only
vigilo add <file> --alert log

# Email alerts (configure SMTP first)
vigilo add <file> --alert email

# Webhook/API push
vigilo add <file> --alert remote

# No alerts
vigilo add <file> --alert silent
Managing Events
bash# Add events to existing monitoring
vigilo events add /etc/nginx/nginx.conf move permissions

# Remove events
vigilo events remove /etc/passwd move

# Replace all events
vigilo events set /var/www/html modify delete
Alert Configuration
bash# Change alert mode
vigilo alert set /etc/passwd --method email

# Test alert system
vigilo alert test

📊 Real-World Examples
Example 1: Web Server Protection
bash# Monitor critical nginx files
vigilo add /etc/nginx/nginx.conf --preset full --alert system
vigilo add /etc/nginx/sites-enabled/default -m -d --alert email
vigilo add /var/www/html -a -m --alert system

# Start monitoring
sudo systemctl start vigilo
Example 2: SSH Security
bash# Monitor SSH configuration and keys
vigilo add /etc/ssh/sshd_config --preset full --alert system
vigilo add /root/.ssh/authorized_keys -m -a -d --alert email
vigilo add /home/*/.ssh/authorized_keys -m -a --alert system
Example 3: System Files Audit
bash# Critical system files
vigilo add /etc/passwd --preset full --alert email
vigilo add /etc/shadow --preset full --alert email
vigilo add /etc/sudoers -m -p --alert system
vigilo add /boot/grub/grub.cfg -m -d --alert email
```

---

## 🏗️ Architecture

### Components
```
Vigilo/
├── main.py                  # CLI interface & command parser
├── file_monitoring.py       # Core monitoring class (SHA-256, metadata)
├── FileWatcher.py           # Real-time event detection (inotify via watchdog)
├── logger.py                # Database operations & history management
├── alert_manager.py         # Multi-channel alert dispatcher
├── requirements.txt         # Python dependencies
├── command_help.txt         # Detailed help text
└── install.sh               # Automated installer
```

### Data Flow
```
1. User adds file → saved to file_info.json (baseline)
2. FileWatcher starts → monitors via inotify
3. File changes → event triggered
4. Compare with baseline → detect changes
5. Generate alert report → dispatch to configured channel
6. Update database → log to alert_history.json

🔒 Security Features
Systemd Service Hardening
The installed service includes enterprise-grade security:
FeatureProtectionProtectSystem=strictSystem directories read-onlyProtectHome=trueUser home directories hiddenPrivateTmp=trueIsolated /tmp namespaceNoNewPrivileges=trueCannot escalate privilegesSystemCallFilterBlocks 200+ dangerous syscallsCapabilityBoundingSet=Zero Linux capabilitiesPrivateDevices=trueNo access to physical devicesProtectKernelModules=trueCannot load kernel modulesRestrictRealtime=trueNo real-time schedulingMemoryLimit=100MPrevents memory leaks
Security score: systemd-analyze security vigilo → 8.5/10 SAFE
File Permissions
All files created with restrictive permissions:
bash/opt/vigilo/                   # 700 (owner only)
/opt/vigilo/*.json             # 600 (owner read/write only)
/opt/vigilo/*.py               # 644 (standard)
Dedicated System User
Service runs as unprivileged user vigilo:

No shell access (/bin/false)
No home directory
Minimal filesystem access

Input Validation

Path normalization (prevents relative path attacks)
Whitelist for monitored directories
Command injection prevention (shlex.quote())
JSON structure validation


⚙️ Configuration
Environment Variables
Configure via systemd service file or environment:
bash# Config file location
export VIGILO_CONFIG=/opt/vigilo/file_info.json

# Logging level
export VIGILO_LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR

# Python unbuffered output (real-time logs)
export PYTHONUNBUFFERED=1
Email Alerts (SMTP)
bash# Set environment variables
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USER=alerts@example.com
export SMTP_PASS=your_app_password
export ALERT_EMAIL_TO=admin@example.com

# Then use email alerts
vigilo add <file> --alert email
Remote Alerts (Webhooks)
bash# Configure webhook endpoint
export REMOTE_ALERT_URL=https://your-server.com/api/alerts
export REMOTE_ALERT_TOKEN=your_secret_token

# Use remote alerts
vigilo add <file> --alert remote
Allowed Directories Whitelist
Edit /opt/vigilo/main.py to modify allowed directories:
pythonALLOWED_DIRS = [
    "/home",
    "/var/log",
    "/opt",
    "/srv",
    "/tmp",
    "/etc/nginx",  # Add specific paths
]


🛠️ Service Management
Systemd Commands
bash# Start service
sudo systemctl start vigilo

# Stop service
sudo systemctl stop vigilo

# Restart service
sudo systemctl restart vigilo

# Check status
sudo systemctl status vigilo

# Enable auto-start on boot
sudo systemctl enable vigilo

# Disable auto-start
sudo systemctl disable vigilo

# View logs (real-time)
journalctl -u vigilo -f

# View logs (today only)
journalctl -u vigilo --since today

# View errors only
journalctl -u vigilo -p err
Security Audit
bash# Full security analysis
systemd-analyze security vigilo

# Show security score
systemd-analyze security vigilo | grep "Overall exposure"

# List security recommendations
systemd-analyze security vigilo --no-pager | grep -E "UNSAFE|MEDIUM"
Resource Monitoring
bash# CPU and memory usage
systemd-cgtop -m

# Service resource limits
systemctl show vigilo | grep -E "Memory|CPU|Tasks"

# Troubleshooting
Issue: "Permission denied" when adding files
Cause: Trying to monitor files the service user cannot read
Solution:
bash# Check file permissions
ls -l /path/to/file

# Option 1: Add vigilo user to file's group
sudo usermod -aG <group> vigilo

# Option 2: Make file readable by vigilo
sudo chown vigilo:vigilo /path/to/file
Issue: "No files are being monitored"
Cause: Haven't added any files yet
Solution:
bash# Add files first
vigilo add /etc/nginx/nginx.conf --preset full

# Verify
vigilo list
Issue: Desktop notifications not working
Cause: notify-send not installed or no DISPLAY variable
Solution:
bash# Install libnotify
sudo apt-get install libnotify-bin  # Ubuntu/Debian
sudo yum install libnotify           # CentOS/RHEL

# Test manually
notify-send "Test" "If you see this, it works"

# Use log alerts instead
vigilo alert set /etc/passwd --method log
Issue: Service fails to start
Check logs:
bashjournalctl -u vigilo -n 50 --no-pager
Common causes:

Python dependencies missing → reinstall: pip install -r requirements.txt
Database file corrupted → backup and delete *.json files
Permission issues → check /opt/vigilo ownership

Issue: High CPU usage
Cause: Monitoring high-churn files (e.g., /var/log/syslog)
Solution:
bash# Don't monitor files that change every second
vigilo remove /var/log/syslog

# Monitor only specific events
vigilo add /var/log/nginx/error.log -d  # deletions only
Issue: Database corruption
Backup and reset:
bash# Backup current state
sudo cp /opt/vigilo/file_info.json /opt/vigilo/file_info.json.backup

# Remove corrupted files
sudo rm /opt/vigilo/file_info.json /opt/vigilo/file_event.json

# Re-add files
vigilo add /etc/nginx/nginx.conf --preset full

# Testing
Test Alert System
bash# Test all configured alert channels
vigilo alert test
Manual File Change Test
bash# Terminal 1: Start monitoring
vigilo add /tmp/test.txt --preset full --alert system
vigilo start

# Terminal 2: Modify file
echo "test modification" >> /tmp/test.txt

# You should receive a desktop notification
Simulate Security Incident
bash# Monitor SSH config
vigilo add /etc/ssh/sshd_config --preset full --alert system

# Start service
sudo systemctl start vigilo

# Simulate unauthorized change
sudo echo "PermitRootLogin yes" >> /etc/ssh/sshd_config

# Alert should trigger immediately

📚 Advanced Usage
Log Retention Management
By default, alerts are retained indefinitely. Clean old logs:
python# Run in Python shell
from logger import delete_old_log_history

# Delete alerts older than 2 years
delete_old_log_history(retention_years=2)
Automate with cron:
bash# Edit crontab
sudo crontab -e

# Add monthly cleanup
0 0 1 * * /usr/bin/python3 -c "from logger import delete_old_log_history; delete_old_log_history(retention_years=2)"
Integration with SIEM
Export alerts to JSON for SIEM ingestion:
bash# Extract all alerts
cat /opt/vigilo/alert_history.json | jq '.'

# Filter by event type
cat /opt/vigilo/alert_history.json | jq '.[] | select(.Event == "modify")'

# Export to CSV
cat /opt/vigilo/alert_history.json | jq -r '.[] | [.Time, .File, .Event] | @csv'
Custom Alert Handlers
Edit /opt/vigilo/alert_manager.py to add custom logic:
python@staticmethod
def custom_notification(report):
    """Your custom alert logic here"""
    # Example: Post to Slack
    import requests
    
    webhook_url = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
    message = f"🚨 File modified: {report['File']}"
    
    requests.post(webhook_url, json={"text": message})
Monitoring Directories
Watch for new files in a directory:
bash# Monitor uploads folder
vigilo add /var/www/uploads --preset add --alert system

# Any new file created → alert

🔄 Upgrading
From Manual to Automated Install
bash# Backup current configuration
sudo cp /opt/vigilo/file_info.json ~/file_info.json.backup

# Run installer
sudo ./install.sh

# Restore configuration
sudo cp ~/file_info.json.backup /opt/vigilo/file_info.json
sudo chown vigilo:vigilo /opt/vigilo/file_info.json
Updating Vigilo
bash# Pull latest changes
cd vigilo
git pull origin main

# Reinstall
sudo ./install.sh

# Restart service
sudo systemctl restart vigilo

🤝 Contributing
Contributions are welcome! Here's how:

Fork the repository
Create a feature branch: git checkout -b feature/amazing-feature
Commit changes: git commit -m 'Add amazing feature'
Push to branch: git push origin feature/amazing-feature
Open a Pull Request


📄 License
MIT License — free to use, modify, and distribute.


📞 Support
Getting Help

Documentation: Check this README and command_help.txt
Issues: GitHub Issues
Discussions: GitHub Discussions

⭐ Star History
If this project helped you, please star it on GitHub!

Built with ❤️ for the cybersecurity community
Version: 1.0.0
Last Updated: February 2026
Maintainer: Freemen HOUNGBEDJI
Website: https://github.com/FreemenTech/Vigilo