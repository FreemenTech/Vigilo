#!/usr/bin/env python3
import os
import stat
import pwd
import grp
import json
import hashlib
from datetime import datetime


class MonitoredFile:
    """
    Represents a file or directory under surveillance.
    """
    
    def __init__(self, path):
        """
        Initialize a MonitoredFile object.
        """
        self.path = os.path.abspath(path)
        
        # File metadata attributes
        self.type = None
        self.file_name = None
        self.size = None
        self.owner = None
        self.group = None
        self.permissions = None
        self.last_modified = None
        self.checksum = None
    
    # =========================================================================
    # METADATA COLLECTION
    # =========================================================================
    
    def file_type(self):
        """
        Determine the type of the filesystem object.
        """
        if os.path.isfile(self.path):
            return "file"
        elif os.path.isdir(self.path):
            return "directory"
        else:
            return "other"
    
    def compute_checksum(self):
        """
        Calculate SHA-256 checksum of the file content.
        """
        if self.type != "file":
            return None
        
        sha = hashlib.sha256()
        
        try:
            with open(self.path, "rb") as f:
                # Read in 4KB chunks to avoid loading entire file into memory
                for chunk in iter(lambda: f.read(4096), b""):
                    sha.update(chunk)
            return sha.hexdigest()
        
        except FileNotFoundError:
            # File was deleted between type check and hash computation
            return None
        
        except PermissionError:
            # Cannot read file (permission denied)
            return None
        
        except OSError as e:
            # Other OS-level errors (disk I/O, etc.)
            return None
    
    def load_file_info(self):
        """
        Collect all metadata about the monitored file.
        Returns:
            dict: Structured metadata in JSON-compatible format
        """
        try:
            stats = os.stat(self.path)
        except (FileNotFoundError, PermissionError, OSError) as e:
            raise e
        
        self.type = self.file_type()
        self.file_name = os.path.basename(self.path)
        self.size = stats.st_size
        
        # Safe owner/group resolution with fallback
        try:
            self.owner = pwd.getpwuid(stats.st_uid).pw_name
        except KeyError:
            self.owner = str(stats.st_uid)  # UID does not exist
        
        try:
            self.group = grp.getgrgid(stats.st_gid).gr_name
        except KeyError:
            self.group = str(stats.st_gid)  # GID does not exist
        
        self.permissions = stat.filemode(stats.st_mode)
        self.last_modified = datetime.fromtimestamp(stats.st_mtime).isoformat()
        self.checksum = self.compute_checksum()
        
        return self.format_json()
    
    # =========================================================================
    # JSON SERIALIZATION
    # =========================================================================
    
    def format_json(self):
        """
        Format collected metadata as structured JSON.
        """
        return {
            "file": {
                "name": self.file_name,
                "path": self.path,
                "type": self.type
            },
            "metadata": {
                "size": self.size,
                "permissions": self.permissions,
                "owner": self.owner,
                "group": self.group,
                "last_modified": self.last_modified,
                "checksum": self.checksum
            }
        }
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    def save_initial_info(self, watch_event, alert_mode):
        """Save initial file state to the monitoring database."""

        data = self.load_file_info()
        
        # Add monitoring configuration
        data["monitoring"] = {
            "watch_events": watch_event,
            "alert_mode": alert_mode,
            "added_on": datetime.now().isoformat()
        }
        # Append as newline-delimited JSON
        # Security: File permissions should be 0o600 (owner-only)
        with open("/opt/vigilo/file_info.json", "a") as f:
            f.write(json.dumps(data) + "\n")
    
    def get_current_info(self):
        """
        Retrieve current state of the monitored file.
        """
        if not os.path.exists(self.path):
            return {
                "file": {
                    "path": self.path
                },
                "deleted": True
            }
        
        try:
            return self.load_file_info()
        except (FileNotFoundError, PermissionError, OSError):
            # File disappeared or became inaccessible
            return {
                "file": {
                    "path": self.path
                },
                "deleted": True
            }

# =============================================================================
# VALIDATION UTILITIES
# =============================================================================

def validate_path(path, allowed_dirs=None):
    abs_path = os.path.abspath(path)
    
    # Optional: Restrict to allowed directories
    if allowed_dirs:
        if not any(abs_path.startswith(d) for d in allowed_dirs):
            return False
    
    # Block obviously dangerous paths (extend as needed)
    forbidden_patterns = [
        "/etc/shadow",
        "/etc/passwd",
        "/root/.ssh",
        "/proc",
        "/sys"
    ]
    
    for pattern in forbidden_patterns:
        if abs_path.startswith(pattern):
            return False
    
    return True