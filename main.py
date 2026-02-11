#!/usr/bin/env python3
import argparse
import sys
import os
import json
import threading
import time
import signal

# Local imports
from file_monitoring import MonitoredFile, validate_path
from FileWatcher import FileWatcher
from logger import (
    is_file_already_monitored,
    get_all_monitored_paths,
    show_file_monitored_info,
    show_all_file_monitored,
    remove_monitored_file_info,
    remove_file_event,
    set_conf,
    show_command_help,
    initialize_database
)
from alert_manager import AlertManager, test_alert_system

# Database file paths
FILE_INFO_DB = "/opt/vigilo/file_info.json"
FILE_EVENT_DB = "/opt/vigilo/file_event.json"

# Allowed directories for monitoring
ALLOWED_DIRS = ["/home","/var/log","/opt","/srv","/tmp"]

# Global watcher instance (for signal handling)
_watcher_instance = None


# =============================================================================
# DATABASE INITIALIZATION
# =============================================================================

def ensure_db_exists():
    """
    Create database files if they don't exist
    """
    initialize_database(FILE_INFO_DB, FILE_EVENT_DB)


# =============================================================================
# COMMAND: ADD
# =============================================================================

def command_add(args):
    ensure_db_exists()
    
    # =========================================================================
    # Parse watch events from arguments
    # =========================================================================
    
    watch_events = []
    
    # Individual flags
    if args.modify:
        watch_events.append("modify")
    if args.delete:
        watch_events.append("delete")
    if args.move:
        watch_events.append("move")
    if args.permissions:
        watch_events.append("permissions")
    if args.add:
        watch_events.append("add")
    
    # Presets override individual flags
    if args.preset == "full":
        watch_events = ["modify", "delete", "move", "permissions", "add"]
    elif args.preset == "default":
        watch_events = ["modify", "delete", "permissions"]
    
    # Validate that at least one event is specified
    if not watch_events:
        print("No watch events specified.")
        print("   Use --preset full/default or specify events with -m, -d, -v, -p, -a")
        sys.exit(1)
    
    # =========================================================================
    # Validate alert mode
    # =========================================================================
    
    if not AlertManager.validate_alert_mode(args.alert):
        print(f" Invalid alert mode: {args.alert}")
        print(f"   Valid modes: {', '.join(['system', 'log', 'email', 'remote', 'silent'])}")
        sys.exit(1)
    
    # =========================================================================
    # Get existing monitored paths for duplicate detection
    # =========================================================================
    
    existing_paths = get_all_monitored_paths(FILE_INFO_DB)
    
    # =========================================================================
    # Process each file
    # =========================================================================
    
    added_count = 0
    
    for path in args.files:
        # Normalize to absolute path
        abs_path = os.path.abspath(path)
        
        # Check if file exists
        if not os.path.exists(abs_path):
            print(f"⚠️ File not found: {abs_path}")
            continue
        
        # Security: Validate path against whitelist
        if not validate_path(abs_path, ALLOWED_DIRS):
            print(f"⚠️ Path not allowed: {abs_path}")
            print(f" Allowed directories: {', '.join(ALLOWED_DIRS)}")
            continue
        
        # Check for duplicates
        if abs_path in existing_paths:
            print(f"⚠️ Already monitoring: {abs_path}")
            continue
        
        # Add to database
        try:
            mf = MonitoredFile(abs_path)
            mf.save_initial_info(
                watch_event=watch_events,
                alert_mode=args.alert
            )
            
            print(f"✅ Added to monitoring: {abs_path}")
            print(f"   Events: {', '.join(watch_events)}")
            print(f"   Alert mode: {args.alert}")
            
            added_count += 1
            existing_paths.add(abs_path)  # Update for next iteration
        
        except (PermissionError, OSError) as e:
            print(f"❌ Cannot access file: {abs_path}")
            print(f"   Error: {e}")
    
    # Summary
    if added_count > 0:
        print(f"\n✅ Successfully added {added_count} file(s) to monitoring")
    else:
        print("\n⚠️  No files were added")

# =============================================================================
# COMMAND: REMOVE
# =============================================================================

def command_remove(args):
    """
    Remove a file from monitoring.
    """
    ensure_db_exists()
    
    abs_path = os.path.abspath(args.file)
    
    # Check if file is being monitored
    if not is_file_already_monitored(abs_path, FILE_INFO_DB):
        print(f"File is not being monitored: {abs_path}")
        sys.exit(1)
    
    # Remove from both databases
    removed_info = remove_monitored_file_info(abs_path, FILE_INFO_DB)
    removed_event = remove_file_event(abs_path, FILE_EVENT_DB)
    
    if removed_info or removed_event:
        print(f"Removed from monitoring: {abs_path}")
    else:
        print(f"Failed to remove: {abs_path}")
        sys.exit(1)


# =============================================================================
# COMMAND: LIST
# =============================================================================

def command_list(args):
    ensure_db_exists()
    
    monitored_files = show_all_file_monitored(FILE_INFO_DB)
    
    if not monitored_files:
        print(" No files are currently being monitored")
        print(" Use 'vigilo add <file>' to start monitoring")
        return
    
    print(f"\nMonitoring {len(monitored_files)} file(s):")
    print("=" * 80)
    
    for file_info in monitored_files:
        path = file_info.get("path", "Unknown")
        file_type = file_info.get("type", "unknown")
        events = file_info.get("watch_events", [])
        alert_mode = file_info.get("alert_mode", "unknown")
        added_on = file_info.get("added_on", "Unknown")
        
        # Format added_on timestamp
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(added_on)
            added_on = dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            pass
        
        print(f"\n{path}")
        print(f"   Type:       {file_type}")
        print(f"   Events:     {', '.join(events)}")
        print(f"   Alert mode: {alert_mode}")
        print(f"   Added:      {added_on}")
    
    print("\n" + "=" * 80)

# =============================================================================
# COMMAND: INFO
# =============================================================================

def command_info(args):
    """
    Show detailed information about a monitored file.
    """
    ensure_db_exists()
    
    abs_path = os.path.abspath(args.file)
    
    file_info = show_file_monitored_info(abs_path, FILE_INFO_DB)
    
    if not file_info:
        print(f"File is not being monitored: {abs_path}")
        sys.exit(1)
    
    # Pretty-print as JSON
    print("\n" + "=" * 80)
    print(f"FILE MONITORING INFORMATION")
    print("=" * 80)
    print(json.dumps(file_info, indent=2))
    print("=" * 80)


# =============================================================================
# COMMAND: ALERT
# =============================================================================

def command_alert(args):
    """
    Configure alert settings for a monitored file.
    """
    ensure_db_exists()
    
    if args.alert_subcommand == "set":
        # Set alert mode for a file
        abs_path = os.path.abspath(args.file)
        
        # Check if file is monitored
        if not is_file_already_monitored(abs_path, FILE_INFO_DB):
            print(f"❌ File is not being monitored: {abs_path}")
            sys.exit(1)
        
        # Validate alert mode
        if not AlertManager.validate_alert_mode(args.method):
            print(f"❌ Invalid alert mode: {args.method}")
            print(f"   Valid modes: {', '.join(['system', 'log', 'email', 'remote', 'silent'])}")
            sys.exit(1)
        
        # Update configuration
        success = set_conf(
            path=abs_path,
            change_type="SET_ALERT",
            new_alert_mode=args.method,
            file_info=FILE_INFO_DB,
            file_event=FILE_EVENT_DB
        )
        
        if success:
            print(f"✅ Alert mode updated: {abs_path}")
            print(f"   New mode: {args.method}")
        else:
            print(f"❌ Failed to update alert mode")
            sys.exit(1)
    
    elif args.alert_subcommand == "test":
        # Test alert system
        test_alert_system()
    
    else:
        print("❌ Unknown alert subcommand")
        print("   Use 'vigilo alert set' or 'vigilo alert test'")
        sys.exit(1)


# =============================================================================
# COMMAND: START
# =============================================================================

def command_start(args):
    """
    Start the file monitoring service.
    """
    ensure_db_exists()
    
    # Check if any files are monitored
    monitored_files = show_all_file_monitored(FILE_INFO_DB)
    
    if not monitored_files:
        print("⚠️  No files are being monitored")
        print("   Use 'vigilo add <file>' to add files before starting")
        sys.exit(1)
    
    print(" Starting VIGILO File Integrity Monitoring Service")
    print("=" * 80)
    
    # Create watcher instance
    global _watcher_instance
    fw = FileWatcher(FILE_INFO_DB, FILE_EVENT_DB)
    _watcher_instance = fw
    
    # Install signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        """Handle shutdown signals gracefully."""
        print(f"\n Received signal {signum}, shutting down...")
        if _watcher_instance and _watcher_instance.observer:
            _watcher_instance.observer.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start monitoring (this blocks until interrupted)
    try:
        fw.start()
    except Exception as e:
        print(f"\n Monitoring service crashed: {e}")
        sys.exit(1)


# =============================================================================
# COMMAND: HELP
# =============================================================================

def command_help(args):
    """
    Display help text from command_help.txt.
    
    Args:
        args: Parsed arguments (no specific args for help)
    """
    help_text = show_command_help("command_help.txt")
    print(help_text)


# =============================================================================
# COMMAND: EVENTS (manage watch events for a file)
# =============================================================================

def command_events(args):
    """
    Manage watch events for a monitored file.
    """
    ensure_db_exists()
    
    abs_path = os.path.abspath(args.file)
    
    # Check if file is monitored
    if not is_file_already_monitored(abs_path, FILE_INFO_DB):
        print(f"File is not being monitored: {abs_path}")
        sys.exit(1)
    
    # Valid event types
    valid_events = {"modify", "delete", "move", "permissions", "add"}
    
    # Validate events
    for event in args.events:
        if event not in valid_events:
            print(f"Invalid event type: {event}")
            print(f"   Valid events: {', '.join(valid_events)}")
            sys.exit(1)
    
    # Perform operation based on subcommand
    if args.events_subcommand == "add":
        # Add events one by one
        for event in args.events:
            success = set_conf(
                path=abs_path,
                change_type="ADD_EVENT",
                new_events=event,
                file_info=FILE_INFO_DB,
                file_event=FILE_EVENT_DB
            )
        
        if success:
            print(f"Events added: {', '.join(args.events)}")
        else:
            print(f"Failed to add events")
            sys.exit(1)
    
    elif args.events_subcommand == "remove":
        # Remove events one by one
        for event in args.events:
            success = set_conf(
                path=abs_path,
                change_type="REMOVE_EVENT",
                new_events=event,
                file_info=FILE_INFO_DB,
                file_event=FILE_EVENT_DB
            )
        
        if success:
            print(f"Events removed: {', '.join(args.events)}")
        else:
            print(f"Failed to remove events")
            sys.exit(1)
    
    elif args.events_subcommand == "set":
        # Replace entire event list
        success = set_conf(
            path=abs_path,
            change_type="SET_EVENTS",
            new_events=args.events,
            file_info=FILE_INFO_DB,
            file_event=FILE_EVENT_DB
        )
        
        if success:
            print(f"Events set to: {', '.join(args.events)}")
        else:
            print(f" Failed to set events")
            sys.exit(1)
    
    else:
        print("Unknown events subcommand")
        print("Use 'vigilo events add', 'vigilo events remove', or 'vigilo events set'")
        sys.exit(1)

# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """
    Main entry point for FIM CLI.
    Parses command-line arguments and dispatches to appropriate command handler.
    """
    parser = argparse.ArgumentParser(
        prog="vigilo",
        description="VIGILO File Integrity Monitoring Tool — Monitor critical files for unauthorized changes",
        epilog="Use 'vigilo <command> --help' for more information on a command"
    )
    
    # Global options
    parser.add_argument(
        "--version",
        action="version",
        version="Vigilo 1.0.0"
    )
    
    # Subcommand parsers
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # =========================================================================
    # COMMAND: add
    # =========================================================================
    
    add_parser = subparsers.add_parser(
        "add",
        help="Add file(s) to monitoring"
    )
    
    add_parser.add_argument(
        "files",
        nargs="+",
        help="File(s) to monitor"
    )
    
    add_parser.add_argument(
        "--preset",
        choices=["full", "default"],
        help="Predefined event set (full: all events, default: modify+delete+permissions)"
    )
    
    add_parser.add_argument(
        "-m", "--modify",
        action="store_true",
        help="Monitor file modifications"
    )
    
    add_parser.add_argument(
        "-d", "--delete",
        action="store_true",
        help="Monitor file deletions"
    )
    
    add_parser.add_argument(
        "-v", "--move",
        action="store_true",
        help="Monitor file moves/renames"
    )
    
    add_parser.add_argument(
        "-p", "--permissions",
        action="store_true",
        help="Monitor permission changes"
    )
    
    add_parser.add_argument(
        "-a", "--add",
        action="store_true",
        help="Monitor file additions (for directories)"
    )
    
    add_parser.add_argument(
        "--alert",
        default="log",
        choices=["system", "log", "email", "remote", "silent"],
        help="Alert mode (default: log)"
    )
    
    add_parser.set_defaults(func=command_add)
    
    # =========================================================================
    # COMMAND: remove
    # =========================================================================
    
    remove_parser = subparsers.add_parser(
        "remove",
        help="Remove file from monitoring"
    )
    
    remove_parser.add_argument(
        "file",
        help="File to remove from monitoring"
    )
    
    remove_parser.set_defaults(func=command_remove)
    
    # =========================================================================
    # COMMAND: list
    # =========================================================================
    
    list_parser = subparsers.add_parser(
        "list",
        help="List all monitored files"
    )
    
    list_parser.set_defaults(func=command_list)
    
    # =========================================================================
    # COMMAND: info
    # =========================================================================
    
    info_parser = subparsers.add_parser(
        "info",
        help="Show detailed information about a monitored file"
    )
    
    info_parser.add_argument(
        "file",
        help="File to inspect"
    )
    
    info_parser.set_defaults(func=command_info)
    
    # =========================================================================
    # COMMAND: start
    # =========================================================================
    
    start_parser = subparsers.add_parser(
        "start",
        help="Start the monitoring service"
    )
    
    start_parser.set_defaults(func=command_start)
    
    # =========================================================================
    # COMMAND: alert
    # =========================================================================
    
    alert_parser = subparsers.add_parser(
        "alert",
        help="Configure alert settings"
    )
    
    alert_subparsers = alert_parser.add_subparsers(dest="alert_subcommand")
    
    # alert set
    alert_set_parser = alert_subparsers.add_parser(
        "set",
        help="Set alert mode for a file"
    )
    
    alert_set_parser.add_argument(
        "file",
        help="File to configure"
    )
    
    alert_set_parser.add_argument(
        "--method",
        required=True,
        choices=["system", "log", "email", "remote", "silent"],
        help="Alert method"
    )
    
    # alert test
    alert_test_parser = alert_subparsers.add_parser(
        "test",
        help="Test alert system"
    )
    
    alert_parser.set_defaults(func=command_alert)
    
    # =========================================================================
    # COMMAND: events
    # =========================================================================
    
    events_parser = subparsers.add_parser(
        "events",
        help="Manage watch events for a file"
    )
    
    events_subparsers = events_parser.add_subparsers(dest="events_subcommand")
    
    # events add
    events_add_parser = events_subparsers.add_parser(
        "add",
        help="Add event(s) to watch list"
    )
    
    events_add_parser.add_argument(
        "file",
        help="File to configure"
    )
    
    events_add_parser.add_argument(
        "events",
        nargs="+",
        choices=["modify", "delete", "move", "permissions", "add"],
        help="Event(s) to add"
    )
    
    # events remove
    events_remove_parser = events_subparsers.add_parser(
        "remove",
        help="Remove event(s) from watch list"
    )
    
    events_remove_parser.add_argument(
        "file",
        help="File to configure"
    )
    
    events_remove_parser.add_argument(
        "events",
        nargs="+",
        choices=["modify", "delete", "move", "permissions", "add"],
        help="Event(s) to remove"
    )
    
    # events set
    events_set_parser = events_subparsers.add_parser(
        "set",
        help="Set watch events (replace existing)"
    )
    
    events_set_parser.add_argument(
        "file",
        help="File to configure"
    )
    
    events_set_parser.add_argument(
        "events",
        nargs="+",
        choices=["modify", "delete", "move", "permissions", "add"],
        help="Event(s) to watch"
    )
    
    events_parser.set_defaults(func=command_events)
    
    # =========================================================================
    # COMMAND: help
    # =========================================================================
    
    help_parser = subparsers.add_parser(
        "help",
        help="Show detailed help"
    )
    
    help_parser.set_defaults(func=command_help)
    
    # =========================================================================
    # Parse and execute
    # =========================================================================
    
    args = parser.parse_args()
    
    # Show help if no command specified
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Execute command
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()