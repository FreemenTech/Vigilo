#!/usr/bin/env python3
import os
import json
import time
import threading
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Local import
from file_monitoring import MonitoredFile
from alert_manager import AlertManager


class FileWatcher:
    """
    Monitors files listed in file_info.json and triggers alerts
    when configured events occur.
    """
    
    # Mapping of user-friendly event names to watchdog event types
    EVENT_MAPPING = {
        "modify": ["modified"],
        "delete": ["deleted"],
        "move": ["moved"],
        "permissions": ["metadata_changed"],  # Simulated via metadata
        "add": ["created"]
    }
    
    def __init__(self, monitored_files_path="/opt/vigilo/file_info.json", event_file_path="/opt/vigilo/file_event.json"):
    
        self.monitored_files_path = monitored_files_path
        self.event_file_path = event_file_path
        
        # Load monitored files configuration
        self.monitored = self.load_files_monitored()
        
        # Performance: Cache baseline states in memory
        self.baseline_cache = {}
        self.load_all_baselines()
        
        # Thread safety: Lock for write operations
        self.write_lock = threading.Lock()
        self.cache_lock = threading.Lock()

        # Load baselines
        self.load_all_baselines()  
        
        # Watchdog observer for filesystem events
        self.observer = Observer()
    
    # =========================================================================
    # INITIALIZATION & CONFIGURATION LOADING
    # =========================================================================
    
    def load_files_monitored(self):
        monitored = {}
        
        if not os.path.exists(self.monitored_files_path):
            return monitored
        
        try:
            with open(self.monitored_files_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        path = data.get("file", {}).get("path")
                        config = data.get("monitoring", {})
                        
                        if path and config:
                            monitored[path] = config
                    
                    except json.JSONDecodeError:
                        # Skip corrupted JSON entries
                        continue
                    except KeyError:
                        # Skip malformed entries
                        continue
        
        except (FileNotFoundError, PermissionError, OSError):
            # Cannot read database file
            return {}
        
        return monitored
    
    def load_all_baselines(self):
        if not os.path.exists(self.monitored_files_path):
            return
        
        with self.cache_lock:
            try:
                with open(self.monitored_files_path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        try:
                            data = json.loads(line)
                            path = data.get("file", {}).get("path")
                            
                            if path:
                                self.baseline_cache[path] = data
                        
                        except json.JSONDecodeError:
                            continue
            
            except (FileNotFoundError, PermissionError, OSError):
                pass
    
    def load_baseline(self, path):
    
        # Try cache first (fast path)
        with self.cache_lock:
            if path in self.baseline_cache:
                return self.baseline_cache[path]
        
        # Fallback: Read from file (slow path)
        # This only happens if cache is stale or corrupted
        if not os.path.exists(self.monitored_files_path):
            return None
        
        try:
            with open(self.monitored_files_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        if data.get("file", {}).get("path") == path:
                            # Update cache for next time
                            with self.cache_lock:
                                self.baseline_cache[path] = data
                            return data
                    
                    except json.JSONDecodeError:
                        continue
        
        except (FileNotFoundError, PermissionError, OSError):
            pass
        
        return None
    
    # =========================================================================
    # FILE EVENT INDEX MANAGEMENT
    # =========================================================================
    
    def save_event_file(self):
        
        monitored = self.load_files_monitored()
        
        index_file = {
            path: {
                "watch_events": cfg.get("watch_events", []),
                "alert_mode": cfg.get("alert_mode")
            }
            for path, cfg in monitored.items()
        }
        
        with self.write_lock:
            # Atomic write: write to temp file, then rename
            temp_path = self.event_file_path + ".tmp"
            
            try:
                with open(temp_path, "w") as f:
                    json.dump(index_file, f, indent=4)
                
                # Atomic rename (POSIX guarantees atomicity)
                os.replace(temp_path, self.event_file_path)
            
            except (OSError, IOError) as e:
                # Clean up temp file on error
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass
    
    # =========================================================================
    # METADATA COMPARISON
    # =========================================================================
    
    @staticmethod
    def compare_metadata(old, new):
      
        changes = {}
        
        # Only compare metadata section (ignore file/monitoring sections)
        old_meta = old.get("metadata", {})
        new_meta = new.get("metadata", {})
        
        for key in old_meta:
            old_value = old_meta.get(key)
            new_value = new_meta.get(key)
            
            if old_value != new_value:
                changes[key] = {
                    "before": old_value,
                    "after": new_value
                }
        
        return changes
    
    # =========================================================================
    # WATCHDOG EVENT HANDLER
    # =========================================================================
    
    class Handler(FileSystemEventHandler):
        """
        Internal handler for watchdog events.
        """
        
        def __init__(self, parent):
            super().__init__()
            self.parent = parent
        
        def dispatch(self, event):
            """
            Intercept all filesystem events and filter by configuration.
            """
            # Normalize path for consistent lookup
            path = os.path.abspath(event.src_path)
            
            # Only process monitored files
            if path not in self.parent.monitored:
                return
            
            # Get user configuration for this file
            cfg = self.parent.monitored[path]
            user_events = cfg.get("watch_events", [])
            
            # Map watchdog event type to our simplified types
            event_type = None
            
            if event.event_type == "modified":
                event_type = "modify"
            elif event.event_type == "deleted":
                event_type = "delete"
            elif event.event_type == "created":
                event_type = "add"
            elif event.event_type == "moved":
                event_type = "move"
            
            # Only process if user wants this event type
            if event_type and event_type in user_events:
                self.parent.handle_event(event_type, path)
    
    # =========================================================================
    # EVENT PROCESSING
    # =========================================================================
    
    def handle_event(self, user_event, path):
        """
        Process a filtered filesystem event.
        """
        print(f" Event '{user_event}' detected on {path}")
        
        # Load baseline state
        old_state = self.load_baseline(path)
        if not old_state:
            print("⚠️  No baseline found for this file")
            return
        
        # Get current state
        file_obj = MonitoredFile(path)
        new_state = file_obj.get_current_info()
        
        # Compare metadata
        changes = self.compare_metadata(old_state, new_state)
        
        # No meaningful changes detected (possible false positive)
        if not changes and user_event != "delete":
            return
        
        # Get alert configuration
        alert_mode = self.monitored.get(path, {}).get("alert_mode", "log")
        
        # Build alert report
        report = {
            "File": path,
            "Event": user_event,
            "Time": datetime.now().isoformat(),
            "AlertMode": alert_mode,
            "Owner": new_state.get("metadata", {}).get("owner", "unknown"),
            "Permissions": new_state.get("metadata", {}).get("permissions", "unknown"),
            "Changes": changes,
            "Interpretation": "",
            "Recommendation": ""
        }
        
        # Add context-specific interpretation
        if user_event == "modify":
            report["Interpretation"] = "File content or metadata was modified"
            report["Recommendation"] = "Review changes and verify legitimacy"
        
        elif user_event == "delete":
            report["Interpretation"] = "File was deleted from filesystem"
            report["Recommendation"] = "Restore from backup if unauthorized"
        
        elif user_event == "move":
            report["Interpretation"] = "File was moved or renamed"
            report["Recommendation"] = "Verify new location and update monitoring"
        
        elif user_event == "add":
            report["Interpretation"] = "New file was created"
            report["Recommendation"] = "Verify file origin and legitimacy"
        
        else:
            report["Interpretation"] = "Unknown event type"
            report["Recommendation"] = "Manual investigation required"
        
        # Save to alert history log
        from vigilo2.logger import save_log_history
        save_log_history(report)
        
        # Dispatch alert (non-blocking)
        AlertManager.dispatch(report, alert_mode)
        
        # Update database state
        from vigilo2.logger import update_files_state
        
        with self.write_lock:
            update_files_state(
                file_info_path=self.monitored_files_path,
                file_event_path=self.event_file_path,
                event_type=user_event,
                src_path=path
            )
            
            # Update cache after database write
            if user_event == "delete":
                with self.cache_lock:
                    self.baseline_cache.pop(path, None)
            else:
                # Reload baseline into cache
                if os.path.exists(path):
                    with self.cache_lock:
                        new_baseline = file_obj.get_current_info()
                        new_baseline["monitoring"] = old_state.get("monitoring", {})
                        self.baseline_cache[path] = new_baseline
    
    # =========================================================================
    # MAIN MONITORING LOOP
    # =========================================================================
    
    def start(self):
        """
        Start the file monitoring service.
        """
        print("File Monitoring Service Started")
        print(f" Monitoring {len(self.monitored)} file(s)")
        
        # Collect unique parent directories to watch
        paths_to_watch = set()
        for path in self.monitored:
            parent_dir = os.path.dirname(path)
            if os.path.exists(parent_dir):
                paths_to_watch.add(parent_dir)
        
        # Create event handler
        handler = FileWatcher.Handler(self)
        
        # Install watchers on each directory
        for path in paths_to_watch:
            try:
                self.observer.schedule(handler, path, recursive=False)
                print(f"Watching: {path}")
            except (OSError, IOError) as e:
                print(f"⚠️ Cannot watch {path}: {e}")
        
        # Start watchdog observer
        self.observer.start()
        
        print(" Monitoring active. Press CTRL+C to stop.")
        
        try:
            # Keep alive until interrupted
            while True:
                time.sleep(1)
        
        except KeyboardInterrupt:
            print("\n Shutting down monitoring service...")
            self.observer.stop()
        
        # Wait for all watchdog threads to finish
        self.observer.join()
        print("Service stopped cleanly")


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def reload_watcher_config(watcher):
    """
    Hot-reload configuration without restarting the watcher.
      """
    with watcher.cache_lock:
        watcher.monitored = watcher.load_files_monitored()
        watcher.baseline_cache.clear()
        watcher.load_all_baselines()
    
    print("🔄 Configuration reloaded")