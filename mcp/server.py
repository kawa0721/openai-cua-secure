#!/usr/bin/env python
"""
Model Context Protocol Server for Claude Desktop

This module implements a Model Context Protocol (MCP) server that leverages
the existing CUA (Computer Using Agent) functionality to provide Claude Desktop
with the ability to control web browsers and automate tasks.

Usage:
  python -m mcp.server [--headless] [--log-level LEVEL] [--screenshot MODE]
                      [--capture-console BOOL] [--save-console BOOL]
                      [--console-log-path PATH] [--screenshot-path PATH]

Examples:
  python -m mcp.server                          # Default settings
  python -m mcp.server --headless --log-level ACTION  # Headless with action logs only
  python -m mcp.server --screenshot search      # Only capture search screenshots
  python -m mcp.server --console-log-path ./custom_logs  # Custom log path
"""

import os
import sys
import json
import time
import random
import argparse
import asyncio
import datetime
import logging
from typing import Dict, List, Optional, Any, Tuple, Union, Literal
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Import MCP SDK
try:
    from mcp.server import Server, resource, tool, schema
except ImportError:
    print("MCP SDK not found. Installing...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "mcp"])
    from mcp.server import Server, resource, tool, schema

# Import from existing codebase
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from computers import LocalPlaywrightComputer
from agent.agent import Agent
from utils import (
    LogLevel, ScreenshotMode, AppSettings, configure_app_settings,
    log_info, log_debug, log_action, log_error, save_screenshot
)

# Import tools
from mcp.tools.search_tools import SearchTools
from mcp.tools.debug_tools import DebugTools
from mcp.tools.browser_tools import BrowserTools

# Global variables
agent_instance = None
computer_instance = None
last_screenshot = None
last_result = None
console_logs = []

# Tool instances
search_tools = None
debug_tools = None
browser_tools = None

# Configuration
config = {
    "headless": False,
    "screenshot_mode": "all",  # "all", "important", "none"
    "capture_console": True,
    "save_console": True,
    "console_log_path": "logs/console_capture",
    "screenshot_path": "screenshots",
    "current_page_url": None,
    "log_level": "INFO"
}

# Create server instance
server = Server(name="claude-cua-bridge")

# -------------------------
# Startup and Shutdown
# -------------------------

@server.on_start
async def setup():
    """
    Initialize the computer and agent instances when the server starts.
    """
    global agent_instance, computer_instance, config, search_tools, debug_tools, browser_tools
    try:
        # Create console log directory if enabled
        if config["capture_console"] and config["save_console"]:
            os.makedirs(config["console_log_path"], exist_ok=True)
        
        # Create screenshot directory
        if config["screenshot_mode"] != "none":
            os.makedirs(config["screenshot_path"], exist_ok=True)
        
        # Set up logging
        configure_app_settings(
            headless=config["headless"],
            log_level=LogLevel[config["log_level"]],
            screenshot_mode=ScreenshotMode[config["screenshot_mode"].upper()]
        )
        
        # Initialize browser
        log_info("Initializing browser")
        computer_instance = LocalPlaywrightComputer(headless=config["headless"])
        await computer_instance.__aenter__()
        
        # Initialize agent
        log_info("Initializing agent")
        agent_instance = Agent(computer=computer_instance)
        
        # Initialize tools
        search_tools = SearchTools(computer_instance)
        debug_tools = DebugTools(computer_instance)
        browser_tools = BrowserTools(computer_instance)
        
        # Set up console capture if enabled
        if config["capture_console"]:
            debug_tools.setup_console_capture()
        
        log_info("Agent, Computer, and Tools initialized successfully")
    except Exception as e:
        log_error(f"Failed to initialize: {str(e)}")
        raise

@server.on_shutdown
async def cleanup():
    """
    Clean up resources when the server stops.
    """
    global computer_instance
    if computer_instance:
        log_info("Cleaning up computer resources")
        await computer_instance.__aexit__(None, None, None)
        log_info("Computer cleaned up successfully")

# -------------------------
# Resources
# -------------------------

@server.resource
def get_current_screen() -> dict:
    """
    Get the current screenshot of the browser.
    
    Returns:
        dict: Screenshot data and metadata
    """
    global computer_instance, last_screenshot, config
    if not computer_instance:
        return {"error": "Computer not initialized"}
    
    # Skip if screenshots are disabled
    if config["screenshot_mode"] == "none":
        return {"message": "Screenshot capture is disabled", "config": config}
    
    try:
        screenshot_base64 = computer_instance.screenshot()
        saved_path = save_screenshot(screenshot_base64, directory=config["screenshot_path"])
        last_screenshot = screenshot_base64
        
        # Get current URL if available
        current_url = None
        if computer_instance.environment == "browser" and hasattr(computer_instance, "get_current_url"):
            current_url = computer_instance.get_current_url()
            config["current_page_url"] = current_url
        
        return {
            "screenshot": f"data:image/png;base64,{screenshot_base64}",
            "saved_path": saved_path,
            "url": current_url,
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        log_error(f"Error taking screenshot: {str(e)}")
        return {"error": str(e)}

@server.resource
def get_console_logs() -> dict:
    """
    Get captured console logs from the browser.
    
    Returns:
        dict: Console logs and count
    """
    global debug_tools, config
    
    if not config["capture_console"]:
        return {"message": "Console log capture is disabled", "config": config}
    
    if not debug_tools:
        return {"error": "Debug tools not initialized"}
    
    return debug_tools.get_console_logs(max_entries=100)

@server.resource
def get_current_config() -> dict:
    """
    Get the current server configuration.
    
    Returns:
        dict: Current configuration
    """
    global config
    return {
        **config,
        "timestamp": datetime.datetime.now().isoformat()
    }

@server.resource
def get_page_metadata() -> dict:
    """
    Get metadata about the current page.
    
    Returns:
        dict: Page metadata including title, description, etc.
    """
    global computer_instance
    if not computer_instance or not hasattr(computer_instance, "_page"):
        return {"error": "Browser not initialized"}
    
    try:
        # Get basic page info
        url = computer_instance._page.url()
        title = computer_instance._page.title()
        
        # Extract metadata using JavaScript
        metadata = computer_instance._page.evaluate("""
        () => {
            const result = {
                title: document.title,
                url: window.location.href,
                domain: window.location.hostname,
                description: "",
                keywords: "",
                author: "",
                openGraph: {},
                twitterCard: {},
                favicon: ""
            };
            
            // Get meta tags
            const metaTags = document.getElementsByTagName('meta');
            for (let i = 0; i < metaTags.length; i++) {
                const meta = metaTags[i];
                const name = meta.getAttribute('name');
                const property = meta.getAttribute('property');
                const content = meta.getAttribute('content');
                
                if (name === 'description') result.description = content;
                else if (name === 'keywords') result.keywords = content;
                else if (name === 'author') result.author = content;
                
                // Open Graph
                if (property && property.startsWith('og:')) {
                    const key = property.substring(3);
                    result.openGraph[key] = content;
                }
                
                // Twitter Card
                if (name && name.startsWith('twitter:')) {
                    const key = name.substring(8);
                    result.twitterCard[key] = content;
                }
            }
            
            // Get favicon
            const faviconElement = document.querySelector("link[rel='icon'], link[rel='shortcut icon']");
            if (faviconElement) {
                result.favicon = faviconElement.href;
            }
            
            return result;
        }
        """)
        
        return {
            "status": "success",
            "url": url,
            "title": title,
            "metadata": metadata,
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        log_error(f"Error getting page metadata: {str(e)}")
        return {"error": str(e)}

# -------------------------
# Configuration Tools
# -------------------------

@server.tool
def configure_environment(
    headless: Optional[bool] = None,
    screenshot_mode: Optional[Literal["all", "important", "none"]] = None,
    capture_console: Optional[bool] = None,
    save_console: Optional[bool] = None,
    console_log_path: Optional[str] = None,
    screenshot_path: Optional[str] = None,
    log_level: Optional[Literal["NONE", "ERROR", "INFO", "ACTION", "DEBUG", "ALL"]] = None
) -> dict:
    """
    Configure the MCP server environment.
    
    Args:
        headless: Run browser in headless mode
        screenshot_mode: Screenshot capture mode
        capture_console: Capture console logs
        save_console: Save console logs to disk
        console_log_path: Path to save console logs
        screenshot_path: Path to save screenshots
        log_level: Logging level
    
    Returns:
        dict: Updated configuration
    """
    global config
    
    # Update configuration
    if headless is not None:
        config["headless"] = headless
    if screenshot_mode is not None:
        config["screenshot_mode"] = screenshot_mode
    if capture_console is not None:
        config["capture_console"] = capture_console
    if save_console is not None:
        config["save_console"] = save_console
    if console_log_path is not None:
        config["console_log_path"] = console_log_path
        # Create the directory if it doesn't exist
        if config["capture_console"] and config["save_console"]:
            os.makedirs(config["console_log_path"], exist_ok=True)
    if screenshot_path is not None:
        config["screenshot_path"] = screenshot_path
        # Create the directory if it doesn't exist
        if config["screenshot_mode"] != "none":
            os.makedirs(config["screenshot_path"], exist_ok=True)
    if log_level is not None:
        config["log_level"] = log_level
        # Update logging level
        configure_app_settings(log_level=LogLevel[log_level])
    
    log_info(f"Configuration updated: {json.dumps(config, indent=2)}")
    return {
        "status": "success",
        "message": "Configuration updated successfully",
        "config": config
    }

@server.tool
async def restart_browser(headless: Optional[bool] = None) -> dict:
    """
    Restart the browser with new settings.
    
    Args:
        headless: Run browser in headless mode
    
    Returns:
        dict: Restart result
    """
    global computer_instance, agent_instance, config, search_tools, debug_tools, browser_tools
    
    try:
        # Update headless setting if provided
        if headless is not None:
            config["headless"] = headless
        
        # Clean up existing instance
        if computer_instance:
            log_info("Closing existing browser instance")
            await computer_instance.__aexit__(None, None, None)
        
        # Create new instance
        log_info(f"Starting new browser instance (headless: {config['headless']})")
        computer_instance = LocalPlaywrightComputer(headless=config["headless"])
        await computer_instance.__aenter__()
        
        # Create new agent
        agent_instance = Agent(computer=computer_instance)
        
        # Update tool instances
        search_tools.set_computer(computer_instance)
        debug_tools.set_computer(computer_instance)
        browser_tools.set_computer(computer_instance)
        
        # Set up console capture
        if config["capture_console"]:
            debug_tools.setup_console_capture()
        
        log_info("Browser restarted successfully")
        
        return {
            "status": "success",
            "message": f"Browser restarted successfully (headless: {config['headless']})"
        }
    except Exception as e:
        log_error(f"Error restarting browser: {str(e)}")
        return {
            "status": "error",
            "message": f"Error restarting browser: {str(e)}"
        }

# -------------------------
# Browser Control Tools
# -------------------------

@server.tool
def navigate_browser(url: str, timeout_ms: Optional[int] = None,
                  wait_until: Optional[str] = None, important_action: bool = True) -> dict:
    """
    Navigate to a URL in the browser.
    
    Args:
        url: The URL to navigate to
        timeout_ms: Custom timeout in milliseconds
        wait_until: Wait until event ('load', 'domcontentloaded', 'networkidle')
        important_action: Whether this is an important action for screenshots
    
    Returns:
        dict: Navigation result
    """
    global browser_tools
    if not browser_tools:
        return {"error": "Browser tools not initialized"}
    
    return browser_tools.navigate(url, timeout_ms, wait_until, None, important_action)

@server.tool
def go_back(timeout_ms: Optional[int] = None, wait_until: Optional[str] = None,
          important_action: bool = False) -> dict:
    """
    Navigate back to the previous page.
    
    Args:
        timeout_ms: Custom timeout in milliseconds
        wait_until: Wait until event ('load', 'domcontentloaded', 'networkidle')
        important_action: Whether this is an important action for screenshots
    
    Returns:
        dict: Navigation result
    """
    global browser_tools
    if not browser_tools:
        return {"error": "Browser tools not initialized"}
    
    return browser_tools.go_back(timeout_ms, wait_until, important_action)

@server.tool
def click_element(selector: str, timeout_ms: Optional[int] = None,
                force: bool = False, important_action: bool = True) -> dict:
    """
    Click an element identified by a CSS selector.
    
    Args:
        selector: CSS selector for the element
        timeout_ms: Custom timeout in milliseconds
        force: Force click even if element not visible
        important_action: Whether this is an important action for screenshots
    
    Returns:
        dict: Click result
    """
    global browser_tools
    if not browser_tools:
        return {"error": "Browser tools not initialized"}
    
    return browser_tools.click_element(selector, timeout_ms, force, important_action)

@server.tool
def type_text(selector: str, text: str, delay: Optional[int] = None,
             clear_first: bool = True, important_action: bool = False) -> dict:
    """
    Type text into an input element.
    
    Args:
        selector: CSS selector for the input element
        text: Text to type
        delay: Delay between keypresses in milliseconds
        clear_first: Whether to clear the input field before typing
        important_action: Whether this is an important action for screenshots
    
    Returns:
        dict: Typing result
    """
    global browser_tools
    if not browser_tools:
        return {"error": "Browser tools not initialized"}
    
    return browser_tools.type_text(selector, text, delay, clear_first, important_action)

@server.tool
def scroll_page(amount: int = 300, smooth: bool = True, 
              humanlike: bool = False, important_action: bool = False) -> dict:
    """
    Scroll the page up or down.
    
    Args:
        amount: Amount to scroll (positive for down, negative for up)
        smooth: Whether to use smooth scrolling
        humanlike: Whether to use random human-like scrolling
        important_action: Whether this is an important action for screenshots
    
    Returns:
        dict: Scrolling result
    """
    global browser_tools
    if not browser_tools:
        return {"error": "Browser tools not initialized"}
    
    return browser_tools.scroll_page(amount, smooth, humanlike, important_action)

@server.tool
def wait_for_element(selector: str, timeout_ms: int = 30000, 
                  state: str = "visible") -> dict:
    """
    Wait for an element to appear in the DOM.
    
    Args:
        selector: CSS selector for the element
        timeout_ms: Maximum time to wait in milliseconds
        state: Element state to wait for ("attached", "detached", "visible", "hidden")
    
    Returns:
        dict: Wait result
    """
    global browser_tools
    if not browser_tools:
        return {"error": "Browser tools not initialized"}
    
    return browser_tools.wait_for_element(selector, timeout_ms, state)

# -------------------------
# CUA Bridge Tool
# -------------------------

@server.tool
def execute_task(task_description: str, important_action: bool = True) -> dict:
    """
    Execute a task using the CUA agent.
    
    Args:
        task_description: Natural language description of the task to perform
        important_action: Whether this is an important action for screenshots
    
    Returns:
        dict: Task execution result
    """
    global agent_instance, computer_instance, config, debug_tools
    if not agent_instance:
        return {"error": "Agent not initialized"}
    
    try:
        # Log the task
        log_info(f"Executing task: {task_description}")
        
        # Clear console logs before task
        if debug_tools and debug_tools.console_capture_enabled:
            debug_tools.clear_console_logs()
        
        # Prepare input for the agent
        items = [{"role": "user", "content": task_description}]
        
        # Execute the task using the CUA agent
        start_time = time.time()
        output_items = agent_instance.run_full_turn(
            items,
            print_steps=True,
            debug=True,
            show_images=False
        )
        elapsed_s = time.time() - start_time
        
        # Extract assistant responses
        assistant_responses = []
        for item in output_items:
            if item.get("role") == "assistant" and item.get("content"):
                assistant_responses.append(item["content"])
        
        final_response = assistant_responses[-1] if assistant_responses else "Task executed"
        
        # Extract action history
        actions = []
        for item in output_items:
            if item.get("type") in ["computer_call", "function_call"]:
                actions.append(item)
        
        # Capture final screenshot
        screenshot_data = {}
        if config["screenshot_mode"] == "all" or (config["screenshot_mode"] == "important" and important_action):
            screenshot_base64 = computer_instance.screenshot()
            saved_path = save_screenshot(screenshot_base64, directory=config["screenshot_path"])
            screenshot_data = {
                "screenshot": f"data:image/png;base64,{screenshot_base64}",
                "saved_path": saved_path
            }
        
        # Update current URL
        if computer_instance.environment == "browser" and hasattr(computer_instance, "get_current_url"):
            config["current_page_url"] = computer_instance.get_current_url()
        
        # Include console logs if enabled
        console_data = {}
        if debug_tools and debug_tools.console_capture_enabled:
            logs_result = debug_tools.get_console_logs(max_entries=20)
            console_data = {
                "console_logs": logs_result.get("logs", []),
                "log_count": logs_result.get("total_count", 0),
                "has_more_logs": logs_result.get("total_count", 0) > 20
            }
        
        # Return result
        return {
            "status": "success",
            "message": final_response,
            "task": task_description,
            "actions_performed": len(actions),
            "elapsed_s": elapsed_s,
            "url": config["current_page_url"],
            "timestamp": datetime.datetime.now().isoformat(),
            **screenshot_data,
            **console_data
        }
    except Exception as e:
        log_error(f"Error executing task: {str(e)}")
        return {"status": "error", "message": str(e)}

# -------------------------
# Search Tools
# -------------------------

@server.tool
def resilient_search(query: str, params: Optional[dict] = None) -> dict:
    """
    Perform a search using multiple search engines with fallback.
    
    Args:
        query: Search query
        params: Search parameters (language, region, etc.)
    
    Returns:
        dict: Search results
    """
    global search_tools
    if not search_tools:
        return {"error": "Search tools not initialized"}
    
    # Determine screenshot mode based on config
    take_screenshots = True
    if config["screenshot_mode"] == "none":
        take_screenshots = False
    
    return search_tools.resilient_search(query, params, humanlike=True, take_screenshots=take_screenshots)

# -------------------------
# Debug Tools
# -------------------------

@server.tool
def clear_console_logs() -> dict:
    """
    Clear the captured console logs.
    
    Returns:
        dict: Result of clearing logs
    """
    global debug_tools
    if not debug_tools:
        return {"error": "Debug tools not initialized"}
    
    return debug_tools.clear_console_logs()

@server.tool
def inject_console_logger(selector: str = "*", events: List[str] = ["click", "input", "change"],
                       capture_values: bool = True, prefix: str = "[EVENT]") -> dict:
    """
    Inject a console logger for DOM events.
    
    Args:
        selector: CSS selector for elements to monitor
        events: List of events to monitor
        capture_values: Whether to capture element values
        prefix: Log message prefix
    
    Returns:
        dict: Logger injection result
    """
    global debug_tools
    if not debug_tools:
        return {"error": "Debug tools not initialized"}
    
    return debug_tools.inject_console_logger(selector, events, capture_values, prefix)

@server.tool
def execute_javascript(code: str, timeout_ms: int = 5000) -> dict:
    """
    Execute JavaScript code in the browser.
    
    Args:
        code: JavaScript code to execute
        timeout_ms: Execution timeout in milliseconds
    
    Returns:
        dict: JavaScript execution result
    """
    global debug_tools
    if not debug_tools:
        return {"error": "Debug tools not initialized"}
    
    return debug_tools.execute_javascript(code, timeout_ms)

@server.tool
def analyze_page_performance(include_resource_details: bool = False) -> dict:
    """
    Analyze the performance of the current page.
    
    Args:
        include_resource_details: Whether to include detailed resource information
    
    Returns:
        dict: Performance analysis
    """
    global debug_tools
    if not debug_tools:
        return {"error": "Debug tools not initialized"}
    
    return debug_tools.analyze_page_performance(include_resource_details)

# -------------------------
# Main Function
# -------------------------

def main():
    """
    Run the MCP server with command line arguments.
    """
    parser = argparse.ArgumentParser(description="Claude Desktop MCP Server")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode"
    )
    parser.add_argument(
        "--log-level",
        choices=["NONE", "ERROR", "INFO", "ACTION", "DEBUG", "ALL"],
        default="INFO",
        help="Set the logging level"
    )
    parser.add_argument(
        "--screenshot",
        choices=["none", "important", "all"],
        default="all",
        help="Control when screenshots are taken"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to run the server on (default: auto-select)"
    )
    parser.add_argument(
        "--capture-console",
        choices=["true", "false"],
        default="true",
        help="Enable or disable console log capture"
    )
    parser.add_argument(
        "--save-console",
        choices=["true", "false"],
        default="true",
        help="Enable or disable saving console logs to disk"
    )
    parser.add_argument(
        "--console-log-path",
        type=str,
        default="logs/console_capture",
        help="Path to save console logs"
    )
    parser.add_argument(
        "--screenshot-path",
        type=str,
        default="screenshots",
        help="Path to save screenshots"
    )
    args = parser.parse_args()
    
    # Update config from command line arguments
    global config
    config["headless"] = args.headless
    config["screenshot_mode"] = args.screenshot
    config["log_level"] = args.log_level
    config["capture_console"] = args.capture_console.lower() == "true"
    config["save_console"] = args.save_console.lower() == "true"
    config["console_log_path"] = args.console_log_path
    config["screenshot_path"] = args.screenshot_path
    
    # Check for required environment variables
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        print("ERROR: OPENAI_API_KEY environment variable is not set.")
        print("Please add this to your .env file or set it in your environment.")
        sys.exit(1)
    
    # Start the server
    print(f"Starting Claude Desktop MCP Server...")
    print(f"Configuration:")
    print(f"  Headless Mode: {config['headless']}")
    print(f"  Log Level: {config['log_level']}")
    print(f"  Screenshot Mode: {config['screenshot_mode']}")
    print(f"  Console Capture: {config['capture_console']}")
    print(f"  Save Console Logs: {config['save_console']}")
    print(f"  Console Log Path: {config['console_log_path']}")
    print(f"  Screenshot Path: {config['screenshot_path']}")
    print(f"\nPress Ctrl+C to stop the server")
    
    # Run the server
    server.run(port=args.port)

if __name__ == "__main__":
    main()
