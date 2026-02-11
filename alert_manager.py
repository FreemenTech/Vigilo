#!/usr/bin/env python3
import subprocess
import shlex
import os
import json
from datetime import datetime


class AlertManager:
    """
    Central dispatcher for all alert types.
    """
    
    # =========================================================================
    # MAIN DISPATCH ROUTER
    # =========================================================================
    
    @staticmethod
    def dispatch(report, alert_mode):
        """
        Route alert to appropriate handler based on mode.
        """
        if not isinstance(report, dict):
            return
        
        if not isinstance(alert_mode, str):
            return
        
        # Route to appropriate handler
        if alert_mode == "system":
            AlertManager.system_notification(report)
        
        elif alert_mode == "log":
            # Already handled by save_log_history in FileWatcher
            pass
        
        elif alert_mode == "email":
            AlertManager.email_notification(report)
        
        elif alert_mode == "remote":
            AlertManager.remote_notification(report)
        
        elif alert_mode == "silent":
            # Explicitly do nothing
            pass
        
        else:
            # Unknown alert mode, fail silently
            pass
    
    # =========================================================================
    # SYSTEM NOTIFICATIONS (Linux Desktop)
    # =========================================================================
    
    @staticmethod
    def system_notification(report):
        """
        Send desktop notification using notify-send(linux).
        """
        # Extract report fields with safe defaults
        file_path = report.get("File", "Unknown file")
        event = report.get("Event", "Unknown event")
        time = report.get("Time", "Unknown time")
        changes = report.get("Changes", {})
        
        # Build notification title
        title = "⚠️ File Monitoring Alert"
        
        # Build notification message
        message_parts = [
            f"File: {file_path}",
            f"Event: {event}",
            f"Time: {time}",
            "",
            "Changes:"
        ]
        
        if not changes:
            message_parts.append("- No detailed changes detected")
        else:
            for field, change in changes.items():
                before = change.get("before", "N/A")
                after = change.get("after", "N/A")
                
                # Truncate long values (e.g., checksums)
                if isinstance(before, str) and len(before) > 50:
                    before = before[:47] + "..."
                if isinstance(after, str) and len(after) > 50:
                    after = after[:47] + "..."
                
                message_parts.append(f"- {field}: {before} → {after}")
        
        message = "\n".join(message_parts)
        
        # Limit total message length to prevent UI issues
        if len(message) > 500:
            message = message[:497] + "..."
        
        # Send notification
        try:
            # Security: Quote all arguments to prevent injection
            subprocess.run(
                [
                    "notify-send",
                    "--urgency=normal",
                    "--icon=dialog-warning",
                    shlex.quote(title),
                    shlex.quote(message)
                ],
                check=False,  # Don't raise on non-zero exit
                timeout=5,    # Kill after 5 seconds if hanging
                stdout=subprocess.DEVNULL,  # Suppress output
                stderr=subprocess.DEVNULL
            )
        
        except FileNotFoundError:
            # notify-send not installed (non-Linux or minimal system)
            pass
        
        except subprocess.TimeoutExpired:
            # notify-send hung (rare)
            pass
        
        except Exception:
            # Any other error (permission denied, etc.)
            # Never crash the watcher
            pass
    
    # =========================================================================
    # EMAIL NOTIFICATIONS
    # =========================================================================
    
    @staticmethod
    def email_notification(report):
        """Send alert via email"""
        
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        # Get SMTP config from environment
        smtp_host = os.environ.get("SMTP_HOST")
        smtp_port = int(os.environ.get("SMTP_PORT", 587))
        smtp_user = os.environ.get("SMTP_USER")
        smtp_pass = os.environ.get("SMTP_PASS")
        to_email = os.environ.get("ALERT_EMAIL_TO")
        
        if not all([smtp_host, smtp_user, smtp_pass, to_email]):
            print("⚠️  Email not configured (missing SMTP env vars)")
            return
        
        # Build email
        subject = f"🚨 Vigilo Alert: {report.get('Event')} on {os.path.basename(report.get('File', 'unknown'))}"
        
        body = f"""
                File Integrity Monitoring Alert

                File: {report.get('File', 'Unknown')}
                Event: {report.get('Event', 'Unknown')}
                Time: {report.get('Time', 'Unknown')}

                Changes Detected:
                """
        
        changes = report.get('Changes', {})
        if changes:
            for field, change in changes.items():
                body += f"\n  {field}:"
                body += f"\n    Before: {change.get('before', 'N/A')}"
                body += f"\n    After:  {change.get('after', 'N/A')}"
        else:
            body += "\n  No detailed changes detected"
        
        body += f"\n\nInterpretation: {report.get('Interpretation', 'N/A')}"
        body += f"\nRecommendation: {report.get('Recommendation', 'N/A')}"
        body += "\n\n---\nVigilo File Integrity Monitoring"
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        # Send
        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
            print(f"Email alert sent to {to_email}")
        
        except Exception as e:
            print(f"⚠️  Failed to send email: {e}")
    
    # =========================================================================
    # REMOTE NOTIFICATIONS
    # =========================================================================
    @staticmethod
    def remote_notification(report):
        """Send alert to remote monitoring server"""
        
        try:
            import requests
        except ImportError:
            print("⚠️ 'requests' library not installed (pip install requests)")
            return
        
        # Get remote config from environment
        url = os.environ.get("REMOTE_ALERT_URL")
        token = os.environ.get("REMOTE_ALERT_TOKEN")
        
        if not url or not token:
            print("⚠️ Remote alert not configured (missing URL/token)")
            return
        
        # Prepare headers
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "Vigilo/1.0"
        }
        
        # Send POST request
        try:
            response = requests.post(
                url,
                json=report,
                headers=headers,
                timeout=5,
                verify=True  # Validate SSL cert
            )
            
            if response.status_code == 200:
                print(f"🌐 Remote alert sent successfully")
            else:
                print(f"⚠️  Remote alert failed: HTTP {response.status_code}")
        
        except requests.exceptions.Timeout:
            print("⚠️  Remote alert timeout (>5s)")
        
        except requests.exceptions.SSLError:
            print("⚠️  Remote alert SSL error (invalid certificate)")
        
        except Exception as e:
            print(f"⚠️  Remote alert failed: {e}")
   
    # =========================================================================
    # ALERT VALIDATION
    # =========================================================================
    
    @staticmethod
    def validate_alert_mode(mode):
        valid_modes = {"system", "log", "email", "remote", "silent"}
        return mode in valid_modes
    
    @staticmethod
    def get_available_modes():
        available = ["log", "silent"]
        
        # Check if notify-send is available
        try:
            subprocess.run(
                ["which", "notify-send"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=1
            )
            available.append("system")
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # Check if email is configured
        smtp_configured = all([
            os.environ.get("SMTP_HOST"),
            os.environ.get("SMTP_USER"),
            os.environ.get("SMTP_PASS"),
            os.environ.get("ALERT_EMAIL_TO")
        ])
        if smtp_configured:
            available.append("email")
        
        # Check if remote is configured
        remote_configured = all([
            os.environ.get("REMOTE_ALERT_URL"),
            os.environ.get("REMOTE_ALERT_TOKEN")
        ])
        if remote_configured:
            available.append("remote")
        
        return available


# =============================================================================
# ALERT FORMATTING UTILITIES
# =============================================================================

def format_alert_summary(report):
    lines = []
    lines.append("=" * 60)
    lines.append(f"FILE MONITORING ALERT")
    lines.append("=" * 60)
    lines.append(f"File:        {report.get('File', 'Unknown')}")
    lines.append(f"Event:       {report.get('Event', 'Unknown')}")
    lines.append(f"Time:        {report.get('Time', 'Unknown')}")
    lines.append(f"Owner:       {report.get('Owner', 'Unknown')}")
    lines.append(f"Permissions: {report.get('Permissions', 'Unknown')}")
    lines.append("")
    
    changes = report.get("Changes", {})
    if changes:
        lines.append("Changes Detected:")
        for field, change in changes.items():
            before = change.get("before", "N/A")
            after = change.get("after", "N/A")
            lines.append(f"  {field}:")
            lines.append(f"    Before: {before}")
            lines.append(f"    After:  {after}")
    else:
        lines.append("No detailed changes detected")
    
    lines.append("")
    lines.append(f"Interpretation: {report.get('Interpretation', 'N/A')}")
    lines.append(f"Recommendation: {report.get('Recommendation', 'N/A')}")
    lines.append("=" * 60)
    
    return "\n".join(lines)


def save_alert_to_file(report, filepath="latest_alert.txt"):
    """
    Save most recent alert to a file.
        """
    try:
        summary = format_alert_summary(report)
        
        with open(filepath, "w") as f:
            f.write(summary)
        
        os.chmod(filepath, 0o600)
    
    except (OSError, IOError):
        pass


# =============================================================================
# TESTING UTILITIES
# =============================================================================

def test_alert_system():
    test_report = {
        "File": "/tmp/test_file.txt",
        "Event": "modify",
        "Time": datetime.now().isoformat(),
        "AlertMode": "test",
        "Owner": "testuser",
        "Permissions": "-rw-r--r--",
        "Changes": {
            "size": {"before": 0, "after": 100}
        },
        "Interpretation": "This is a test alert",
        "Recommendation": "No action needed"
    }
    
    print("\n Testing alert system...")
    print("=" * 60)
    
    available = AlertManager.get_available_modes()
    print(f"Available alert modes: {', '.join(available)}")
    print("")
    
    for mode in available:
        if mode in ["log", "silent"]:
            continue  # Skip silent mode
        
        print(f"Testing {mode} alert...")
        AlertManager.dispatch(test_report, mode)
        print(f"{mode} alert dispatched")
    
    print("=" * 60)
    print("Alert system test complete")