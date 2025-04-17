import os
import requests
from dotenv import load_dotenv
import json
import base64
from PIL import Image
from io import BytesIO
import io
import sys
import datetime
import time
import enum
from urllib.parse import urlparse
from typing import Optional, Literal

load_dotenv(override=True)

# Define log levels as an enum
class LogLevel(enum.Enum):
    NONE = 0    # No logging
    ERROR = 1   # Only errors
    INFO = 2    # Basic informational messages
    ACTION = 3  # Browser actions only
    DEBUG = 4   # Detailed debug information
    ALL = 5     # All possible logging

# Define screenshot modes
class ScreenshotMode(enum.Enum):
    NONE = "none"      # No screenshots
    SEARCH = "search"  # Screenshots only during search operations
    ALL = "all"        # Screenshots for all operations

# Screenshot configuration
class ScreenshotConfig:
    """Configuration for screenshot behavior and optimization"""
    
    def __init__(
        self,
        mode: ScreenshotMode = ScreenshotMode.ALL,
        format: Literal["png", "jpeg"] = "jpeg",
        quality: int = 85,
        max_files: int = 100,
        compare_threshold: float = 0.95,
        cleanup_interval: int = 10,
        screenshot_path: str = "screenshots"
    ):
        self.mode = mode
        self.format = format
        self.quality = max(1, min(100, quality))
        self.max_files = max_files
        self.compare_threshold = compare_threshold
        self.cleanup_interval = cleanup_interval
        self.screenshot_count = 0  # Counter to trigger periodic cleanup
        self.screenshot_path = screenshot_path
        
    def should_take_screenshot(self, context: Optional[str] = None) -> bool:
        """Check if a screenshot should be taken in the current context"""
        if self.mode == ScreenshotMode.NONE:
            return False
        elif self.mode == ScreenshotMode.SEARCH:
            return context == "search" if context else False
        else:  # ScreenshotMode.ALL
            return True
    
    def increment_counter(self) -> bool:
        """
        Increments screenshot counter and returns True if cleanup should be performed
        """
        self.screenshot_count += 1
        return self.screenshot_count % self.cleanup_interval == 0

# Application settings class
# Navigation timeout configuration
class NavigationConfig:
    """Configuration for navigation behavior and timeouts"""
    
    def __init__(
        self,
        default_timeout: int = 30000,  # milliseconds
        wait_until: Literal["load", "domcontentloaded", "networkidle", "commit"] = "networkidle",
        ajax_timeout: int = 5000,  # milliseconds
        auto_adjust: bool = True,
        min_timeout: int = 5000,  # milliseconds
        max_timeout: int = 60000,  # milliseconds
        slow_mo: int = 0,  # milliseconds to slow down each operation
        dynamic_content_timeout: int = 2000  # milliseconds to wait for dynamic content
    ):
        self.default_timeout = default_timeout
        self.wait_until = wait_until
        self.ajax_timeout = ajax_timeout
        self.auto_adjust = auto_adjust
        self.min_timeout = min_timeout
        self.max_timeout = max_timeout
        self.slow_mo = slow_mo
        self.dynamic_content_timeout = dynamic_content_timeout
        
        # Performance tracking for adaptive timeouts
        self.navigation_history = []  # Store recent navigation times
        self.max_history_size = 10
        
    def track_navigation_time(self, url: str, duration_ms: float) -> None:
        """Track navigation time for a URL to adjust future timeouts"""
        self.navigation_history.append({"url": url, "duration_ms": duration_ms, "timestamp": time.time()})
        # Keep only recent history
        if len(self.navigation_history) > self.max_history_size:
            self.navigation_history.pop(0)
    
    def get_timeout_for_url(self, url: str = None) -> int:
        """Calculate appropriate timeout based on history and current network conditions"""
        if not self.auto_adjust or not self.navigation_history:
            return self.default_timeout
            
        # Calculate average navigation time from history
        total_time = sum(entry["duration_ms"] for entry in self.navigation_history)
        avg_time = total_time / len(self.navigation_history)
        
        # Add margin for safety (50% more than average)
        timeout = avg_time * 1.5
        
        # Ensure it's within allowed range
        return max(self.min_timeout, min(int(timeout), self.max_timeout))

class AppSettings:
    """Central settings class for controlling application behavior"""
    
    def __init__(
        self,
        headless: bool = False,
        log_level: LogLevel = LogLevel.INFO, 
        screenshot_mode: ScreenshotMode = ScreenshotMode.ALL,
        log_to_console: bool = True,
        log_to_file: bool = True,
        screenshot_config: ScreenshotConfig = None,
        navigation_config: NavigationConfig = None,
        screenshot_path: str = "screenshots"
    ):
        self.headless = headless
        self.log_level = log_level
        self.screenshot_mode = screenshot_mode
        self.log_to_console = log_to_console
        self.log_to_file = log_to_file
        self.screenshot_path = screenshot_path
        
        # Initialize screenshot config or use provided one
        if screenshot_config:
            self.screenshot_config = screenshot_config
        else:
            self.screenshot_config = ScreenshotConfig(mode=screenshot_mode, screenshot_path=screenshot_path)
        
        # Initialize navigation config or use default
        self.navigation_config = navigation_config or NavigationConfig()
        
    def should_log(self, level: LogLevel) -> bool:
        """Check if a particular log level should be logged with current settings"""
        if self.log_level == LogLevel.NONE:
            return False
        return level.value <= self.log_level.value
        
    def should_take_screenshot(self, context: Optional[str] = None) -> bool:
        """Check if a screenshot should be taken in the current context"""
        # For backward compatibility - uses either the config or the direct mode
        if hasattr(self, 'screenshot_config') and self.screenshot_config:
            return self.screenshot_config.should_take_screenshot(context)
        
        # Legacy behavior
        if self.screenshot_mode == ScreenshotMode.NONE:
            return False
        elif self.screenshot_mode == ScreenshotMode.SEARCH:
            return context == "search" if context else False
        else:  # ScreenshotMode.ALL
            return True

# Global settings instance with defaults
SETTINGS = AppSettings()

# Setup logging to file
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_file = f"{log_dir}/console_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Create a custom stdout logger
class Logger(object):
    def __init__(self, filename="console.log", settings: AppSettings = None):
        self.terminal = sys.stdout
        self.log = open(filename, "a") if os.path.exists(log_dir) else None
        self.settings = settings or SETTINGS
        
    def write(self, message):
        if self.settings.log_to_console:
            self.terminal.write(message)
        if self.settings.log_to_file and self.log:
            self.log.write(message)
            self.log.flush()

    def flush(self):
        self.terminal.flush()
        if self.log:
            self.log.flush()
            
    def update_settings(self, settings: AppSettings):
        """Update logger settings"""
        self.settings = settings

# Redirect stdout to our custom logger
sys.stdout = Logger(log_file)

BLOCKED_DOMAINS = [
    "maliciousbook.com",
    "evilvideos.com",
    "darkwebforum.com",
    "shadytok.com",
    "suspiciouspins.com",
    "ilanbigio.com",
]


def pp(obj):
    """Pretty print an object as JSON"""
    formatted = json.dumps(obj, indent=4)
    # Only print if logging is enabled
    if SETTINGS.log_level != LogLevel.NONE:
        print(formatted)
    return formatted

def log_info(message):
    """Log informational message"""
    if SETTINGS.should_log(LogLevel.INFO):
        print(f"[INFO] {message}")
    
def log_debug(message):
    """Log debug message"""
    if SETTINGS.should_log(LogLevel.DEBUG):
        print(f"[DEBUG] {message}")
    
def log_action(action, details=None):
    """Log an action with optional details"""
    if SETTINGS.should_log(LogLevel.ACTION):
        if details:
            print(f"[ACTION] {action} - {details}")
        else:
            print(f"[ACTION] {action}")

def log_error(message):
    """Log error message"""
    if SETTINGS.should_log(LogLevel.ERROR):
        print(f"[ERROR] {message}")
        
def set_log_level(level: LogLevel):
    """Set the global log level"""
    SETTINGS.log_level = level
    
def configure_app_settings(
    headless: bool = None,
    log_level: LogLevel = None,
    screenshot_mode: ScreenshotMode = None,
    log_to_console: bool = None,
    log_to_file: bool = None,
    screenshot_config: ScreenshotConfig = None,
    navigation_config: NavigationConfig = None,
    screenshot_path: str = None
):
    """Update global application settings with provided values"""
    if headless is not None:
        SETTINGS.headless = headless
    if log_level is not None:
        SETTINGS.log_level = log_level
    if screenshot_mode is not None:
        SETTINGS.screenshot_mode = screenshot_mode
        # Also update the mode in screenshot_config if it exists
        if hasattr(SETTINGS, 'screenshot_config') and SETTINGS.screenshot_config:
            SETTINGS.screenshot_config.mode = screenshot_mode
    if log_to_console is not None:
        SETTINGS.log_to_console = log_to_console
    if log_to_file is not None:
        SETTINGS.log_to_file = log_to_file
    if screenshot_config is not None:
        SETTINGS.screenshot_config = screenshot_config
    if navigation_config is not None:
        SETTINGS.navigation_config = navigation_config
    if screenshot_path is not None:
        SETTINGS.screenshot_path = screenshot_path
        # Also update the path in screenshot_config if it exists
        if hasattr(SETTINGS, 'screenshot_config') and SETTINGS.screenshot_config:
            SETTINGS.screenshot_config.screenshot_path = screenshot_path
        
    # Update logger settings
    if isinstance(sys.stdout, Logger):
        sys.stdout.update_settings(SETTINGS)


def show_image(base_64_image):
    image_data = base64.b64decode(base_64_image)
    image = Image.open(BytesIO(image_data))
    try:
        image.show()
    except Exception as e:
        print(f"Failed to show image: {e}")
        
def save_screenshot(base_64_image, directory=None, context=None, 
                 quality=None, max_screenshots=None, compare_last=None):
    """
    Save a base64 encoded image to a file with timestamp, with optimizations.
    
    Args:
        base_64_image: Base64 encoded image data
        directory: Directory to save the screenshot in (overrides settings if provided)
        context: Optional context string (e.g., 'search') to determine if screenshot should be taken
        quality: JPEG quality for compression (1-100, higher is better quality but larger file)
                If None, uses the quality from screenshot_config
        max_screenshots: Maximum number of screenshots to keep (oldest will be deleted)
                       If None, uses the max_files from screenshot_config
        compare_last: Whether to compare with last screenshot to avoid duplicates
                    If None, uses comparison based on screenshot_config.compare_threshold
        
    Returns:
        Filename of saved screenshot or None if not saved
    """
    # Check if we should take a screenshot based on settings and context
    if not SETTINGS.should_take_screenshot(context):
        log_debug(f"Screenshot not taken - context: {context}, mode: {SETTINGS.screenshot_mode.name}")
        return None
    
    # Use custom directory if provided, otherwise use the one from settings
    if directory is None:
        if hasattr(SETTINGS, 'screenshot_path') and SETTINGS.screenshot_path:
            directory = SETTINGS.screenshot_path
        elif hasattr(SETTINGS, 'screenshot_config') and SETTINGS.screenshot_config and hasattr(SETTINGS.screenshot_config, 'screenshot_path'):
            directory = SETTINGS.screenshot_config.screenshot_path
        else:
            directory = "screenshots"  # Default fallback
        
    # Use configuration values if parameters are not provided
    if hasattr(SETTINGS, 'screenshot_config') and SETTINGS.screenshot_config:
        config = SETTINGS.screenshot_config
        quality = quality if quality is not None else config.quality
        max_screenshots = max_screenshots if max_screenshots is not None else config.max_files
        compare_last = compare_last if compare_last is not None else (config.compare_threshold > 0)
    else:
        # Default values if no config available
        quality = quality if quality is not None else 85
        max_screenshots = max_screenshots if max_screenshots is not None else 100
        compare_last = compare_last if compare_last is not None else True
    
    import os
    import datetime
    import hashlib
    from pathlib import Path
    
    # Create directory if it doesn't exist
    if not os.path.exists(directory):
        os.makedirs(directory)
    
    # Generate filename with timestamp and optional context
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    context_str = f"_{context}" if context else ""
    
    try:
        # Decode image
        image_data = base64.b64decode(base_64_image)
        image = Image.open(BytesIO(image_data))
        
        # Check if this image is similar to the last screenshot with the same context
        if compare_last:
            # Find last screenshot with the same context
            pattern = f"*{context_str}.jpg" if context else "*.jpg"
            screenshot_dir = Path(directory)
            matching_files = sorted(list(screenshot_dir.glob(pattern)), 
                                   key=lambda x: x.stat().st_mtime, reverse=True)
            
            if matching_files:
                # Calculate hash of current image content
                current_hash = hashlib.md5(image_data).hexdigest()
                
                # Open last image and calculate its hash
                try:
                    last_image = Image.open(matching_files[0])
                    last_buffer = BytesIO()
                    last_image.save(last_buffer, format="PNG")
                    last_hash = hashlib.md5(last_buffer.getvalue()).hexdigest()
                    
                    # If hashes are the same (or very similar), skip saving
                    if current_hash == last_hash:
                        log_debug(f"Screenshot skipped - identical to previous image: {matching_files[0].name}")
                        return str(matching_files[0])
                except Exception as hash_err:
                    log_debug(f"Failed to compare screenshot hashes: {hash_err}")
        
        # Determine file format from config
        format_name = "jpeg"  # Default format
        if hasattr(SETTINGS, 'screenshot_config') and SETTINGS.screenshot_config:
            format_name = SETTINGS.screenshot_config.format
        
        # Set file extension based on format
        extension = ".jpg" if format_name.lower() == "jpeg" else ".png"
        filename = f"{directory}/screenshot_{timestamp}{context_str}{extension}"
        
        # Convert to RGB if the image is in RGBA mode and we're using JPEG (which doesn't support alpha)
        if format_name.lower() == "jpeg" and image.mode == 'RGBA':
            log_debug("Converting RGBA image to RGB for JPEG format")
            rgb_image = Image.new('RGB', image.size, (255, 255, 255))
            rgb_image.paste(image, mask=image.split()[3])  # Use alpha channel as mask
            image = rgb_image
        
        # Save with appropriate format and options
        if format_name.lower() == "jpeg":
            image.save(filename, format="JPEG", quality=quality, optimize=True)
            log_debug(f"Saved JPEG with quality {quality}")
        else:
            # For PNG, use different optimization parameters
            image.save(filename, format="PNG", optimize=True, compress_level=6)
            log_debug("Saved PNG with compression")
        
        # Log the save operation
        file_size = os.path.getsize(filename) / 1024  # KB
        if SETTINGS.should_log(LogLevel.INFO):
            print(f"Screenshot saved to {filename} ({file_size:.2f} KB)")
        
        # Clean up old screenshots if we exceed the maximum
        if max_screenshots > 0:
            cleanup_old_screenshots(directory, max_screenshots)
            
        return filename
    except Exception as e:
        log_error(f"Failed to save screenshot: {e}")
        return None


def cleanup_old_screenshots(directory="screenshots", max_files=100):
    """
    Delete oldest screenshots when the number exceeds max_files.
    
    Args:
        directory: Directory containing screenshots
        max_files: Maximum number of screenshots to keep
    """
    try:
        from pathlib import Path
        
        # Get all jpg/png files in the directory
        screenshot_dir = Path(directory)
        screenshots = list(screenshot_dir.glob("*.jpg")) + list(screenshot_dir.glob("*.png"))
        
        # Sort by modification time (oldest first)
        screenshots.sort(key=lambda x: x.stat().st_mtime)
        
        # Delete oldest files if we have too many
        if len(screenshots) > max_files:
            files_to_delete = screenshots[:len(screenshots) - max_files]
            deleted_count = 0
            for file in files_to_delete:
                try:
                    file.unlink()
                    deleted_count += 1
                    log_debug(f"Deleted old screenshot: {file.name}")
                except Exception as e:
                    log_error(f"Failed to delete old screenshot {file.name}: {e}")
            
            if deleted_count > 0:
                log_debug(f"Cleaned up {deleted_count} old screenshots")
    except Exception as e:
        log_error(f"Error during screenshot cleanup: {e}")


def calculate_image_dimensions(base_64_image):
    image_data = base64.b64decode(base_64_image)
    image = Image.open(io.BytesIO(image_data))
    return image.size


def sanitize_message(msg: dict) -> dict:
    """Return a copy of the message with image_url omitted for computer_call_output messages."""
    if msg.get("type") == "computer_call_output":
        output = msg.get("output", {})
        if isinstance(output, dict):
            sanitized = msg.copy()
            sanitized["output"] = {**output, "image_url": "[omitted]"}
            return sanitized
    return msg


def create_response(**kwargs):
    url = "https://api.openai.com/v1/responses"
    
    # Use environment variable for API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set")
        
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    openai_org = os.getenv("OPENAI_ORG")
    if openai_org:
        headers["Openai-Organization"] = openai_org

    response = requests.post(url, headers=headers, json=kwargs)

    if response.status_code != 200:
        print(f"Error: {response.status_code} {response.text}")

    return response.json()


def check_blocklisted_url(url: str) -> None:
    """Raise ValueError if the given URL (including subdomains) is in the blocklist."""
    hostname = urlparse(url).hostname or ""
    if any(
        hostname == blocked or hostname.endswith(f".{blocked}")
        for blocked in BLOCKED_DOMAINS
    ):
        raise ValueError(f"Blocked URL: {url}")

def get_latest_log(lines=50):
    """Get the latest log file content."""
    try:
        if not os.path.exists(log_dir):
            return "No logs directory found."
            
        log_files = sorted([f for f in os.listdir(log_dir) if f.startswith("console_")], reverse=True)
        if not log_files:
            return "No log files found."
            
        latest_log = os.path.join(log_dir, log_files[0])
        with open(latest_log, 'r') as f:
            # Get the last N lines
            content = f.readlines()
            return "".join(content[-lines:])
    except Exception as e:
        return f"Error reading log file: {e}"

def get_log_file_content(log_file_path, lines=None):
    """Get content from a specific log file."""
    try:
        if not os.path.exists(log_file_path):
            return f"Log file not found: {log_file_path}"
            
        with open(log_file_path, 'r') as f:
            content = f.readlines()
            if lines:
                return "".join(content[-lines:])
            return "".join(content)
    except Exception as e:
        return f"Error reading log file: {e}"
        
def list_available_logs(limit=10):
    """List available log files with timestamps."""
    if not os.path.exists(log_dir):
        return []
        
    log_files = sorted([f for f in os.listdir(log_dir) if f.startswith("console_")], reverse=True)
    if limit:
        log_files = log_files[:limit]
    
    return [os.path.join(log_dir, f) for f in log_files]

def get_log_info(log_file_path):
    """Get brief information about a log file."""
    try:
        if not os.path.exists(log_file_path):
            return {"error": f"Log file not found: {log_file_path}"}
            
        file_size = os.path.getsize(log_file_path) / 1024  # KB
        
        # Get first and last timestamps from content
        with open(log_file_path, 'r') as f:
            first_lines = [f.readline() for _ in range(10)]
            # Get to the end efficiently by seeking to last 4KB (roughly)
            f.seek(max(0, os.path.getsize(log_file_path) - 4096))
            last_content = f.read()
            last_lines = last_content.split('\n')[-10:]
            
        # Attempt to extract timestamps or other identifiers
        filename = os.path.basename(log_file_path)
        timestamp = filename.replace("console_", "").replace(".log", "")
        
        # Count actions in the log (estimate)
        action_count = 0
        with open(log_file_path, 'r') as f:
            content = f.read()
            action_count = content.count("[ACTION]")
            
        return {
            "path": log_file_path,
            "timestamp": timestamp,
            "size_kb": round(file_size, 2),
            "action_count": action_count,
        }
    except Exception as e:
        return {"error": f"Error analyzing log file: {str(e)}"}
