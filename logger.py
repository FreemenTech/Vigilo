#!/usr/bin/env python3
import os
import json
import threading
from datetime import datetime
from dateutil.relativedelta import relativedelta

# Local imports
from file_monitoring import MonitoredFile

# Global lock for thread-safe database operations
_db_lock = threading.Lock()


# =============================================================================
# ALERT HISTORY MANAGEMENT
# =============================================================================

def save_log_history(report, file="/opt/vigilo/alert_history.json"):
        
    with _db_lock:
        all_reports = []
        
        # Read existing history
        if os.path.exists(file):
            try:
                with open(file, "r") as f:
                    all_reports = json.load(f)
                
                # Validate it's a list
                if not isinstance(all_reports, list):
                    all_reports = []
            
            except json.JSONDecodeError:
                # Corrupted file, start fresh
                all_reports = []
            
            except (OSError, IOError):
                # Cannot read file
                all_reports = []
        
        # Append new report
        all_reports.append(report)
        
        # Atomic write
        temp_file = file + ".tmp"
        
        try:
            with open(temp_file, "w") as f:
                json.dump(all_reports, f, indent=4)
            
            # Set restrictive permissions (owner read/write only)
            os.chmod(temp_file, 0o600)
            
            # Atomic rename
            os.replace(temp_file, file)
        
        except (OSError, IOError) as e:
            # Clean up temp file on error
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass
            
            print(f"⚠️ Error saving alert history: {e}")

def show_log_history(file="/opt/vigilo/alert_history.json"):
    """
    Retrieve complete alert history.
    """
    if not os.path.exists(file):
        return []
    
    try:
        with open(file, "r") as f:
            data = json.load(f)
        
        # Validate structure
        if isinstance(data, list):
            return data
        else:
            return []
    
    except json.JSONDecodeError:
        return []
    
    except (OSError, IOError):
        return []


def delete_old_log_history(file="/opt/vigilo/alert_history.json", retention_years=2):
    """
    Delete alert logs older than 2year.
    """
    if not os.path.exists(file):
        return
    
    with _db_lock:
        try:
            with open(file, "r") as f:
                all_alerts = json.load(f)
        
        except json.JSONDecodeError:
            return
        
        except (OSError, IOError):
            return
        
        # Calculate expiration date
        now = datetime.now()
        expiration_date = now - relativedelta(years=retention_years)
        
        kept_alerts = []
        
        for alert in all_alerts:
            try:
                # Parse alert timestamp
                alert_time = datetime.fromisoformat(alert["Time"])
                
                # Keep if within retention period
                if alert_time >= expiration_date:
                    kept_alerts.append(alert)
            
            except (KeyError, ValueError):
                # Preserve alerts with invalid timestamps (fail-safe)
                kept_alerts.append(alert)
        
        # Atomic write
        temp_file = file + ".tmp"
        
        try:
            with open(temp_file, "w") as f:
                json.dump(kept_alerts, f, indent=4)
            
            os.chmod(temp_file, 0o600)
            os.replace(temp_file, file)
            
            deleted_count = len(all_alerts) - len(kept_alerts)
            print(f"🗑️  Deleted {deleted_count} old alert(s)")
        
        except (OSError, IOError) as e:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass
            
            print(f"⚠️  Error cleaning history: {e}")


# =============================================================================
# MONITORED FILE INFORMATION QUERIES
# =============================================================================

def show_file_monitored_info(path, file="/opt/vigilo/file_info.json"):
    """
    Retrieve detailed information about a monitored file.
    Args:
        path (str): Path to the monitored file
        file (str): Path to file_info.json database
        
    Returns:
        dict: Complete file information, or None if not found
    """
    abs_path = os.path.abspath(path)
    
    if not os.path.exists(file):
        return None
    
    try:
        with open(file, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    
                    if data.get("file", {}).get("path") == abs_path:
                        metadata = data.get("metadata", {})
                        monitoring = data.get("monitoring", {})
                        
                        return {
                            "file_name": data.get("file", {}).get("name"),
                            "path": data.get("file", {}).get("path"),
                            "type": data.get("file", {}).get("type"),
                            "size": metadata.get("size"),
                            "permissions": metadata.get("permissions"),
                            "owner": metadata.get("owner"),
                            "group": metadata.get("group"),
                            "last_modified": metadata.get("last_modified"),
                            "checksum": metadata.get("checksum"),
                            "watch_events": monitoring.get("watch_events", []),
                            "alert_mode": monitoring.get("alert_mode"),
                            "added_on": monitoring.get("added_on")
                        }
                
                except json.JSONDecodeError:
                    continue
    
    except (OSError, IOError):
        return None
    
    return None


def show_all_file_monitored(file="/opt/vigilo/file_info.json"):
    
    all_monitored = []
    
    if not os.path.exists(file):
        return all_monitored
    
    try:
        with open(file, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    monitoring = data.get("monitoring", {})
                    file_info = data.get("file", {})
                    
                    all_monitored.append({
                        "file_name": file_info.get("name"),
                        "path": file_info.get("path"),
                        "type": file_info.get("type"),
                        "watch_events": monitoring.get("watch_events", []),
                        "alert_mode": monitoring.get("alert_mode"),
                        "added_on": monitoring.get("added_on")
                    })
                
                except json.JSONDecodeError:
                    continue
    
    except (OSError, IOError):
        return []
    
    return all_monitored

# =============================================================================
# DUPLICATE DETECTION
# =============================================================================

def is_file_already_monitored(path, file="/opt/vigilo/file_info.json"):
    
    abs_path = os.path.abspath(path)
    
    if not os.path.exists(file):
        return False
    
    try:
        with open(file, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    if data.get("file", {}).get("path") == abs_path:
                        return True
                
                except json.JSONDecodeError:
                    continue
    
    except (OSError, IOError):
        return False
    
    return False

def get_all_monitored_paths(file="/opt/vigilo/file_info.json"):
    monitored_paths = set()
    
    if not os.path.exists(file):
        return monitored_paths
    
    try:
        with open(file, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    path = data.get("file", {}).get("path")
                    if path:
                        monitored_paths.add(path)
                
                except json.JSONDecodeError:
                    continue
    
    except (OSError, IOError):
        return set()
    
    return monitored_paths

# =============================================================================
# FILE REMOVAL OPERATIONS
# =============================================================================

def remove_monitored_file_info(path, file="/opt/vigilo/file_info.json"):
   
    if not os.path.exists(file):
        return False
    
    path = os.path.abspath(path)
    
    with _db_lock:
        new_lines = []
        removed = False
        
        try:
            with open(file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        
                        if data.get("file", {}).get("path") != path:
                            new_lines.append(json.dumps(data))
                        else:
                            removed = True
                    
                    except json.JSONDecodeError:
                        # Preserve corrupted lines (fail-safe)
                        new_lines.append(line)
        
        except (OSError, IOError):
            return False
        
        # Atomic write
        temp_file = file + ".tmp"
        
        try:
            with open(temp_file, "w") as f:
                for line in new_lines:
                    f.write(line + "\n")
            
            os.chmod(temp_file, 0o600)
            os.replace(temp_file, file)
        
        except (OSError, IOError) as e:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass
            
            print(f"⚠️  Error removing file from database: {e}")
            return False
        
        return removed


def remove_file_event(path, file="/opt/vigilo/file_event.json"):
   
    if not os.path.exists(file):
        return False
    
    path = os.path.abspath(path)
    
    with _db_lock:
        try:
            with open(file, "r") as f:
                data = json.load(f)
        
        except json.JSONDecodeError:
            return False
        
        except (OSError, IOError):
            return False
        
        # Remove entry if exists
        removed = False
        if path in data:
            del data[path]
            removed = True
        
        # Atomic write
        temp_file = file + ".tmp"
        
        try:
            with open(temp_file, "w") as f:
                json.dump(data, f, indent=4)
            
            os.chmod(temp_file, 0o600)
            os.replace(temp_file, file)
        
        except (OSError, IOError) as e:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass
            
            print(f"⚠️  Error updating event index: {e}")
            return False
        
        return removed


# =============================================================================
# CONFIGURATION UPDATES
# =============================================================================

def set_conf(path, change_type, new_events=None, new_alert_mode=None,file_info="/opt/vigilo/file_info.json", file_event="/opt/vigilo/file_event.json"):
    path = os.path.abspath(path)
    
    if not os.path.exists(file_info):
        return False
    
    with _db_lock:
        updated_lines = []
        updated = False
        
        # ======================================================================
        # UPDATE file_info.json
        # ======================================================================
        
        try:
            with open(file_info, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        
                        if data.get("file", {}).get("path") == path:
                            monitoring = data.get("monitoring", {})
                            
                            # -------- SET_EVENTS --------
                            if change_type == "SET_EVENTS" and isinstance(new_events, list):
                                monitoring["watch_events"] = new_events
                                updated = True
                            
                            # -------- ADD_EVENT --------
                            elif change_type == "ADD_EVENT" and new_events:
                                events = set(monitoring.get("watch_events", []))
                                events.add(new_events)
                                monitoring["watch_events"] = list(events)
                                updated = True
                            
                            # -------- REMOVE_EVENT --------
                            elif change_type == "REMOVE_EVENT" and new_events:
                                events = set(monitoring.get("watch_events", []))
                                events.discard(new_events)
                                monitoring["watch_events"] = list(events)
                                updated = True
                            
                            # -------- SET_ALERT --------
                            elif change_type == "SET_ALERT" and new_alert_mode:
                                monitoring["alert_mode"] = new_alert_mode
                                updated = True
                            
                            # -------- SET_ALL --------
                            elif change_type == "SET_ALL":
                                if isinstance(new_events, list):
                                    monitoring["watch_events"] = new_events
                                if new_alert_mode:
                                    monitoring["alert_mode"] = new_alert_mode
                                updated = True
                            
                            data["monitoring"] = monitoring
                        
                        updated_lines.append(json.dumps(data))
                    
                    except json.JSONDecodeError:
                        # Preserve corrupted lines
                        updated_lines.append(line)
        
        except (OSError, IOError):
            return False
        
        if not updated:
            return False  # File not found in database
        
        # Atomic write to file_info.json
        temp_file = file_info + ".tmp"
        
        try:
            with open(temp_file, "w") as f:
                for line in updated_lines:
                    f.write(line + "\n")
            
            os.chmod(temp_file, 0o600)
            os.replace(temp_file, file_info)
        
        except (OSError, IOError) as e:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass
            
            print(f"⚠️  Error updating configuration: {e}")
            return False
        
        # ======================================================================
        # REGENERATE file_event.json
        # ======================================================================
        
        try:
            regenerate_event_index(file_info, file_event)
        except Exception as e:
            print(f"⚠️  Error regenerating event index: {e}")
            return False
        
        return True


def regenerate_event_index(file_info="/opt/vigilo/file_info.json", file_event="/opt/vigilo/file_event.json"):
    monitored = {}
    
    if os.path.exists(file_info):
        try:
            with open(file_info, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        path = data.get("file", {}).get("path")
                        monitoring = data.get("monitoring", {})
                        
                        if path:
                            monitored[path] = {
                                "watch_events": monitoring.get("watch_events", []),
                                "alert_mode": monitoring.get("alert_mode")
                            }
                    
                    except json.JSONDecodeError:
                        continue
        
        except (OSError, IOError):
            pass
    
    # Atomic write
    temp_file = file_event + ".tmp"
    
    try:
        with open(temp_file, "w") as f:
            json.dump(monitored, f, indent=4)
        
        os.chmod(temp_file, 0o600)
        os.replace(temp_file, file_event)
    
    except (OSError, IOError) as e:
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass
        
        raise e


# =============================================================================
# DATABASE STATE UPDATES (CALLED BY FILEWATCHER)
# =============================================================================

def update_files_state(file_info_path, file_event_path, event_type, src_path, dest_path=None):
   
    if not os.path.exists(file_info_path):
        return
    
    src_path = os.path.abspath(src_path)
    dest_path = os.path.abspath(dest_path) if dest_path else None
    
    with _db_lock:
        updated_lines = []
        
        try:
            with open(file_info_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        path = data.get("file", {}).get("path")
                        
                        # -------- DELETE --------
                        if event_type == "delete" and path == src_path:
                            # Skip this entry (remove from database)
                            continue
                        
                        # -------- MOVE --------
                        if event_type == "move" and path == src_path and dest_path:
                            if os.path.exists(dest_path):
                                mf = MonitoredFile(dest_path)
                                try:
                                    new_data = mf.load_file_info()
                                    new_data["monitoring"] = data.get("monitoring", {})
                                    updated_lines.append(json.dumps(new_data))
                                except (FileNotFoundError, PermissionError, OSError):
                                    # Destination no longer accessible
                                    pass
                            continue
                        
                        # -------- MODIFY / ADD --------
                        if event_type in ["modify", "add"] and path == src_path:
                            if os.path.exists(src_path):
                                mf = MonitoredFile(src_path)
                                try:
                                    new_data = mf.load_file_info()
                                    new_data["monitoring"] = data.get("monitoring", {})
                                    updated_lines.append(json.dumps(new_data))
                                except (FileNotFoundError, PermissionError, OSError):
                                    # File no longer accessible
                                    updated_lines.append(json.dumps(data))
                            else:
                                # File was deleted, keep old state
                                updated_lines.append(json.dumps(data))
                            continue
                        
                        # -------- UNCHANGED --------
                        updated_lines.append(json.dumps(data))
                    
                    except json.JSONDecodeError:
                        # Preserve corrupted lines
                        updated_lines.append(line)
        
        except (OSError, IOError):
            return
        
        # Atomic write to file_info.json
        temp_file = file_info_path + ".tmp"
        
        try:
            with open(temp_file, "w") as f:
                for line in updated_lines:
                    f.write(line + "\n")
            
            os.chmod(temp_file, 0o600)
            os.replace(temp_file, file_info_path)
        
        except (OSError, IOError) as e:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass
            
            print(f"⚠️  Error updating database state: {e}")
            return
        
        # Regenerate event index
        try:
            regenerate_event_index(file_info_path, file_event_path)
        except Exception as e:
            print(f"⚠️  Error regenerating event index: {e}")


# =============================================================================
# VALIDATION UTILITIES
# =============================================================================

def valid_path(path):
    return os.path.exists(path)

# =============================================================================
# HELP SYSTEM
# =============================================================================

def show_command_help(file="/opt/vigilo/command_help.txt"):
    if not os.path.exists(file):
        return "⚠️  Help file not found"
    
    try:
        with open(file, "r") as f:
            return f.read()
    
    except (OSError, IOError):
        return "⚠️  Cannot read help file"


# =============================================================================
# DATABASE INITIALIZATION
# =============================================================================

def initialize_database(file_info="/opt/vigilo/file_info.json", file_event="/opt/vigilo/file_event.json"):
   
    if not os.path.exists(file_info):
        with open(file_info, "w") as f:
            pass  # Create empty file
        os.chmod(file_info, 0o600)
    
    if not os.path.exists(file_event):
        with open(file_event, "w") as f:
            json.dump({}, f)
        os.chmod(file_event, 0o600)