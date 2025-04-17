#!/usr/bin/env python
"""
CUA to MCP Bridge

This module provides the bridge between the CUA (Computer Using Agent) and MCP (Model Context Protocol)
systems. It adapts the CUA functionality to be used with Claude Desktop through the MCP interface.
"""

import os
import sys
import json
import time
import base64
import asyncio
from typing import Dict, List, Any, Optional, Union, Callable
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from CUA codebase
from agent.agent import Agent
from computers import LocalPlaywrightComputer
from utils import log_info, log_debug, log_error, log_action, save_screenshot

# Import tools
from mcp.tools.search_tools import SearchTools
from mcp.tools.debug_tools import DebugTools
from mcp.tools.browser_tools import BrowserTools


class CUABridge:
    """
    Bridge class that adapts CUA functionality for use with MCP.
    """
    
    def __init__(
        self,
        headless: bool = False,
        model: str = "computer-use-preview",
        acknowledge_callback: Callable = lambda msg: True
    ):
        """
        Initialize the CUA Bridge.
        
        Args:
            headless: Whether to run the browser in headless mode
            model: The model to use for CUA
            acknowledge_callback: Callback function for safety checks
        """
        self.model = model
        self.headless = headless
        self.acknowledge_callback = acknowledge_callback
        self.computer = None
        self.agent = None
        self.search_tools = None
        self.debug_tools = None
        self.browser_tools = None
        self.initialized = False
        self.conversation_history = []
    
    async def initialize(self):
        """
        Initialize the computer and agent.
        """
        if self.initialized:
            return
        
        try:
            # Initialize computer
            log_info(f"Initializing computer (headless: {self.headless})")
            self.computer = LocalPlaywrightComputer(headless=self.headless)
            await self.computer.__aenter__()
            
            # Initialize agent
            log_info(f"Initializing agent with model: {self.model}")
            self.agent = Agent(
                model=self.model,
                computer=self.computer,
                acknowledge_safety_check_callback=self.acknowledge_callback
            )
            
            # Initialize tools
            self.search_tools = SearchTools(self.computer)
            self.debug_tools = DebugTools(self.computer)
            self.browser_tools = BrowserTools(self.computer)
            
            # Set up console capture
            self.debug_tools.setup_console_capture()
            
            self.initialized = True
            log_info("CUA Bridge initialized successfully")
        except Exception as e:
            log_error(f"Failed to initialize CUA Bridge: {str(e)}")
            raise
    
    async def cleanup(self):
        """
        Clean up resources.
        """
        if not self.initialized:
            return
        
        try:
            if self.computer:
                await self.computer.__aexit__(None, None, None)
                self.computer = None
            
            self.agent = None
            self.search_tools = None
            self.debug_tools = None
            self.browser_tools = None
            self.initialized = False
            log_info("CUA Bridge cleaned up successfully")
        except Exception as e:
            log_error(f"Error during CUA Bridge cleanup: {str(e)}")
    
    async def restart(self, headless: Optional[bool] = None):
        """
        Restart the computer and agent.
        
        Args:
            headless: Whether to run the browser in headless mode
        """
        # Update headless setting if provided
        if headless is not None:
            self.headless = headless
        
        # Clean up existing instances
        await self.cleanup()
        
        # Initialize new instances
        await self.initialize()
        
        # Clear conversation history
        self.conversation_history = []
        
        return {"status": "success", "message": "CUA Bridge restarted successfully"}
    
    def get_screenshot(self) -> Optional[str]:
        """
        Get a screenshot from the computer.
        
        Returns:
            Base64-encoded screenshot or None if not available
        """
        if not self.initialized or not self.computer:
            return None
        
        try:
            return self.computer.screenshot()
        except Exception as e:
            log_error(f"Error taking screenshot: {str(e)}")
            return None
    
    def take_screenshot(self, full_page: bool = False, quality: int = 80) -> Dict[str, Any]:
        """
        Take a screenshot of the current page with specific options.
        
        Args:
            full_page: Whether to take a screenshot of the full page or just the viewport
            quality: Quality of the screenshot (1-100)
        
        Returns:
            Result of the screenshot operation
        """
        if not self.initialized or not self.browser_tools:
            return {"status": "error", "message": "CUA Bridge not initialized"}
        
        return self.browser_tools.take_screenshot(full_page, quality)
    
    def navigate(self, url: str, timeout_ms: Optional[int] = None, wait_until: Optional[str] = None) -> Dict[str, Any]:
        """
        Navigate to a URL.
        
        Args:
            url: The URL to navigate to
            timeout_ms: Custom timeout in milliseconds
            wait_until: Wait until event ('load', 'domcontentloaded', 'networkidle')
        
        Returns:
            Result of navigation
        """
        if not self.initialized or not self.browser_tools:
            return {"status": "error", "message": "CUA Bridge not initialized"}
        
        return self.browser_tools.navigate(url, timeout_ms, wait_until)
    
    def execute_task(self, task: str) -> Dict[str, Any]:
        """
        Execute a task using the CUA agent.
        
        Args:
            task: Description of the task to execute
        
        Returns:
            Result of task execution
        """
        if not self.initialized or not self.agent:
            return {"status": "error", "message": "CUA Bridge not initialized"}
        
        try:
            log_info(f"Executing task: {task}")
            
            # Add task to conversation history
            self.conversation_history.append({"role": "user", "content": task})
            
            # Execute task using agent
            output_items = self.agent.run_full_turn(
                self.conversation_history,
                print_steps=True,
                debug=True,
                show_images=False
            )
            
            # Add output items to conversation history
            self.conversation_history.extend(output_items)
            
            # Extract assistant messages
            assistant_messages = []
            for item in output_items:
                if item.get("role") == "assistant" and item.get("content"):
                    assistant_messages.append(item["content"])
            
            # Get final screenshot
            screenshot = self.get_screenshot()
            
            # Get console logs
            console_logs = []
            if self.debug_tools and self.debug_tools.console_capture_enabled:
                logs_result = self.debug_tools.get_console_logs(max_entries=20)
                console_logs = logs_result.get("logs", [])
            
            return {
                "status": "success",
                "message": assistant_messages[-1] if assistant_messages else "Task executed",
                "screenshot": screenshot,
                "items": output_items,
                "console_logs": console_logs,
                "url": self.get_current_url(),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            log_error(f"Error executing task: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def click(self, selector: str, force: bool = False) -> Dict[str, Any]:
        """
        Click an element identified by a CSS selector.
        
        Args:
            selector: CSS selector for the element
            force: Force click even if element not visible
        
        Returns:
            Result of the click operation
        """
        if not self.initialized or not self.browser_tools:
            return {"status": "error", "message": "CUA Bridge not initialized"}
        
        return self.browser_tools.click_element(selector, force=force)
    
    def type_text(self, selector: str, text: str, delay: Optional[int] = None) -> Dict[str, Any]:
        """
        Type text into an input element.
        
        Args:
            selector: CSS selector for the input element
            text: Text to type
            delay: Delay between keypresses in milliseconds
        
        Returns:
            Result of the typing operation
        """
        if not self.initialized or not self.browser_tools:
            return {"status": "error", "message": "CUA Bridge not initialized"}
        
        return self.browser_tools.type_text(selector, text, delay)
    
    def scroll(self, amount: int = 300, smooth: bool = True, humanlike: bool = False) -> Dict[str, Any]:
        """
        Scroll the page.
        
        Args:
            amount: Amount to scroll (positive for down, negative for up)
            smooth: Whether to use smooth scrolling
            humanlike: Whether to use random human-like scrolling
        
        Returns:
            Result of the scroll operation
        """
        if not self.initialized or not self.browser_tools:
            return {"status": "error", "message": "CUA Bridge not initialized"}
        
        return self.browser_tools.scroll_page(amount, smooth, humanlike)
    
    def keypress(self, keys: List[str], delay: Optional[int] = None) -> Dict[str, Any]:
        """
        Press keyboard keys or key combinations.
        
        Args:
            keys: List of keys to press (e.g., ["Control", "c"] for Ctrl+C)
            delay: Delay between keystrokes in milliseconds
        
        Returns:
            Result of the key press operation
        """
        if not self.initialized or not self.browser_tools:
            return {"status": "error", "message": "CUA Bridge not initialized"}
        
        return self.browser_tools.keypress(keys, delay)
    
    def wait_for_element(self, selector: str, timeout_ms: int = 30000, 
                       state: str = "visible") -> Dict[str, Any]:
        """
        Wait for an element to appear in the DOM.
        
        Args:
            selector: CSS selector for the element
            timeout_ms: Maximum time to wait in milliseconds
            state: Element state to wait for ("attached", "detached", "visible", "hidden")
        
        Returns:
            Result of waiting for the element
        """
        if not self.initialized or not self.browser_tools:
            return {"status": "error", "message": "CUA Bridge not initialized"}
        
        return self.browser_tools.wait_for_element(selector, timeout_ms, state)
    
    def setup_network_monitor(self) -> Dict[str, Any]:
        """
        Set up network request/response monitoring.
        
        Returns:
            Result of setting up monitoring
        """
        if not self.initialized or not self.debug_tools:
            return {"status": "error", "message": "CUA Bridge not initialized"}
        
        return self.debug_tools.setup_network_monitor()
    
    def get_network_events(self, max_events: int = 100, filter_url: Optional[str] = None,
                        event_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Get captured network events.
        
        Args:
            max_events: Maximum number of events to return
            filter_url: Filter by URL (substring match)
            event_type: Filter by event type ('request' or 'response')
        
        Returns:
            Result of getting network events
        """
        if not self.initialized or not self.debug_tools:
            return {"status": "error", "message": "CUA Bridge not initialized"}
        
        return self.debug_tools.get_network_events(max_events, filter_url, event_type)
    
    def execute_javascript(self, code: str, timeout_ms: int = 5000) -> Dict[str, Any]:
        """
        Execute JavaScript code in the browser.
        
        Args:
            code: JavaScript code to execute
            timeout_ms: Execution timeout in milliseconds
        
        Returns:
            Result of JavaScript execution
        """
        if not self.initialized or not self.debug_tools:
            return {"status": "error", "message": "CUA Bridge not initialized or debug tools not available"}
        
        return self.debug_tools.execute_javascript(code, timeout_ms)
    
    def get_current_url(self) -> str:
        """
        Get the current URL.
        
        Returns:
            Current URL or empty string if not available
        """
        if not self.initialized or not self.computer or not hasattr(self.computer, "get_current_url"):
            return ""
        
        try:
            return self.computer.get_current_url()
        except Exception as e:
            log_error(f"Error getting current URL: {str(e)}")
            return ""
