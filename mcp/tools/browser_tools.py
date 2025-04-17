#!/usr/bin/env python
"""
Browser Tools for Claude Desktop MCP Server

This module provides browser-related tools for the Claude Desktop MCP server.
It leverages Playwright functionality for browser control and interaction.
"""

import os
import sys
import time
import base64
import random
from typing import Dict, List, Optional, Any
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import from existing codebase
from utils import log_info, log_debug, log_error, log_action, save_screenshot


class BrowserTools:
    """
    Browser operation tools for MCP server.
    """
    
    def __init__(self, computer=None):
        """
        Initialize browser tools with a computer instance.
        
        Args:
            computer: Computer instance for performing browser operations
        """
        self.computer = computer
    
    def set_computer(self, computer):
        """
        Set the computer instance for performing browser operations.
        
        Args:
            computer: Computer instance
        """
        self.computer = computer
    
    def navigate(self, url: str, timeout_ms: Optional[int] = None, 
                wait_until: Optional[str] = None, wait_for_selector: Optional[str] = None,
                important_action: bool = True) -> Dict[str, Any]:
        """
        Navigate to a URL.
        
        Args:
            url: URL to navigate to
            timeout_ms: Custom timeout in milliseconds
            wait_until: Wait until event ('load', 'domcontentloaded', 'networkidle')
            wait_for_selector: Wait for a specific selector to be visible
            important_action: Whether this is an important action for screenshots
        
        Returns:
            dict: Navigation result
        """
        if not self.computer:
            return {"status": "error", "message": "Computer not initialized"}
        
        try:
            # Log the action
            log_action("navigate", f"url={url}")
            
            # Prepare navigation options
            options = {}
            if timeout_ms:
                options["timeout"] = timeout_ms
            if wait_until:
                options["wait_until"] = wait_until
            
            # Navigate to URL
            start_time = time.time()
            self.computer.goto(url, **options)
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            # Wait for selector if specified
            if wait_for_selector:
                try:
                    self.computer._page.wait_for_selector(wait_for_selector, state="visible")
                except Exception as e:
                    log_error(f"Element not found: {wait_for_selector}, error: {str(e)}")
            
            # Take screenshot
            screenshot_base64 = self.computer.screenshot()
            saved_path = save_screenshot(screenshot_base64)
            
            # Get page information
            title = self.computer._page.title()
            current_url = self.computer._page.url()
            
            return {
                "status": "success",
                "message": f"Navigated to {url}",
                "url": current_url,
                "title": title,
                "elapsed_ms": elapsed_ms,
                "screenshot": f"data:image/png;base64,{screenshot_base64}",
                "saved_path": saved_path,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            log_error(f"Error navigating to {url}: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def go_back(self, timeout_ms: Optional[int] = None, wait_until: Optional[str] = None,
               important_action: bool = False) -> Dict[str, Any]:
        """
        Navigate back to the previous page.
        
        Args:
            timeout_ms: Custom timeout in milliseconds
            wait_until: Wait until event ('load', 'domcontentloaded', 'networkidle')
            important_action: Whether this is an important action for screenshots
        
        Returns:
            dict: Navigation result
        """
        if not self.computer or not hasattr(self.computer, "_page"):
            return {"status": "error", "message": "Computer not initialized"}
        
        try:
            # Log the action
            log_action("go_back", "")
            
            # Prepare navigation options
            options = {}
            if timeout_ms:
                options["timeout"] = timeout_ms
            if wait_until:
                options["wait_until"] = wait_until
            
            # Navigate back
            start_time = time.time()
            self.computer._page.go_back(**options)
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            # Take screenshot
            screenshot_base64 = self.computer.screenshot()
            saved_path = save_screenshot(screenshot_base64)
            
            # Get page information
            title = self.computer._page.title()
            current_url = self.computer._page.url()
            
            return {
                "status": "success",
                "message": "Navigated back",
                "url": current_url,
                "title": title,
                "elapsed_ms": elapsed_ms,
                "screenshot": f"data:image/png;base64,{screenshot_base64}",
                "saved_path": saved_path,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            log_error(f"Error navigating back: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def click_element(self, selector: str, timeout_ms: Optional[int] = None,
                     force: bool = False, important_action: bool = True) -> Dict[str, Any]:
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
        if not self.computer or not hasattr(self.computer, "_page"):
            return {"status": "error", "message": "Computer not initialized"}
        
        try:
            # Log the action
            log_action("click_element", f"selector={selector}, force={force}")
            
            # Prepare click options
            options = {}
            if timeout_ms:
                options["timeout"] = timeout_ms
            if force:
                options["force"] = True
            
            # Try to scroll element into view
            try:
                self.computer._page.evaluate(f"""
                    (selector) => {{                        
                        const element = document.querySelector(selector);
                        if (element) {{                            
                            element.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                        }}
                    }}
                """, selector)
                time.sleep(0.5)  # Allow time for scroll to complete
            except Exception as e:
                log_debug(f"Scroll into view failed: {str(e)}")
            
            # Click the element
            start_time = time.time()
            self.computer._page.click(selector, **options)
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            # Wait for potential navigation or DOM changes
            time.sleep(0.8)
            
            # Take screenshot
            screenshot_base64 = self.computer.screenshot()
            saved_path = save_screenshot(screenshot_base64)
            
            # Get page information
            title = self.computer._page.title()
            current_url = self.computer._page.url()
            
            return {
                "status": "success",
                "message": f"Clicked element: {selector}",
                "url": current_url,
                "title": title,
                "elapsed_ms": elapsed_ms,
                "screenshot": f"data:image/png;base64,{screenshot_base64}",
                "saved_path": saved_path,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            log_error(f"Error clicking element {selector}: {str(e)}")
            return {"status": "error", "message": str(e)}

    def keypress(self, keys: List[str], delay: Optional[int] = None) -> Dict[str, Any]:
        """
        Press keyboard keys or key combinations.
        
        Args:
            keys: List of keys to press (e.g., ["Control", "c"] for Ctrl+C)
            delay: Delay between keystrokes in milliseconds
        
        Returns:
            dict: Keypress result
        """
        if not self.computer or not hasattr(self.computer, "_page"):
            return {"status": "error", "message": "Computer not initialized"}
        
        try:
            # Log the action
            log_action("keypress", f"keys={keys}")
            
            # Prepare options
            options = {}
            if delay:
                options["delay"] = delay
            
            # Press keys
            start_time = time.time()
            
            # Handle single key or combination
            if len(keys) == 1:
                self.computer._page.keyboard.press(keys[0], **options)
            else:
                # For key combinations, press all keys down, then release in reverse order
                for key in keys:
                    self.computer._page.keyboard.down(key)
                    if delay:
                        time.sleep(delay / 1000)  # Convert ms to seconds
                
                # Release keys in reverse order
                for key in reversed(keys):
                    self.computer._page.keyboard.up(key)
                    if delay:
                        time.sleep(delay / 1000)
                        
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            # Take screenshot
            screenshot_base64 = self.computer.screenshot()
            saved_path = save_screenshot(screenshot_base64)
            
            return {
                "status": "success",
                "message": f"Pressed keys: {', '.join(keys)}",
                "keys": keys,
                "elapsed_ms": elapsed_ms,
                "screenshot": f"data:image/png;base64,{screenshot_base64}",
                "saved_path": saved_path,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            log_error(f"Error pressing keys {keys}: {str(e)}")
            return {"status": "error", "message": str(e)}

    def take_screenshot(self, full_page: bool = False, quality: int = 80) -> Dict[str, Any]:
        """
        Take a screenshot of the current page.
        
        Args:
            full_page: Whether to take a screenshot of the full page or just the viewport
            quality: Quality of the screenshot (1-100)
        
        Returns:
            dict: Screenshot result
        """
        if not self.computer or not hasattr(self.computer, "_page"):
            return {"status": "error", "message": "Computer not initialized"}
        
        try:
            # Log the action
            log_action("take_screenshot", f"full_page={full_page}, quality={quality}")
            
            # Take screenshot with specified options
            start_time = time.time()
            options = {
                "full_page": full_page,
                "type": "jpeg" if quality < 100 else "png",
            }
            
            if options["type"] == "jpeg":
                options["quality"] = quality
                
            screenshot_bytes = self.computer._page.screenshot(**options)
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            # Convert to base64
            screenshot_base64 = base64.b64encode(screenshot_bytes).decode("utf-8")
            saved_path = save_screenshot(screenshot_base64)
            
            # Get page information
            title = self.computer._page.title()
            current_url = self.computer._page.url()
            
            return {
                "status": "success",
                "message": "Screenshot taken",
                "url": current_url,
                "title": title,
                "full_page": full_page,
                "quality": quality,
                "elapsed_ms": elapsed_ms,
                "format": options["type"],
                "screenshot": f"data:image/{options['type']};base64,{screenshot_base64}",
                "saved_path": saved_path,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            log_error(f"Error taking screenshot: {str(e)}")
            return {"status": "error", "message": str(e)}
            
    def type_text(self, selector: str, text: str, delay: Optional[int] = None,
                 clear_first: bool = True, important_action: bool = False) -> Dict[str, Any]:
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
        if not self.computer or not hasattr(self.computer, "_page"):
            return {"status": "error", "message": "Computer not initialized"}
        
        try:
            # Log the action
            log_action("type_text", f"selector={selector}, text={text}, clear_first={clear_first}")
            
            # Try to scroll element into view
            try:
                self.computer._page.evaluate(f"""
                    (selector) => {{                        
                        const element = document.querySelector(selector);
                        if (element) {{                            
                            element.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                        }}
                    }}
                """, selector)
                time.sleep(0.5)  # Allow time for scroll to complete
            except Exception as e:
                log_debug(f"Scroll into view failed: {str(e)}")
            
            # Focus on the element
            self.computer._page.focus(selector)
            
            # Clear the field if requested
            if clear_first:
                self.computer._page.evaluate(f"""
                    (selector) => {{                        
                        const element = document.querySelector(selector);
                        if (element) {{                            
                            element.value = '';
                        }}
                    }}
                """, selector)
            
            # Type text with or without delay
            start_time = time.time()
            if delay is not None:
                for char in text:
                    self.computer._page.type(selector, char, delay=delay)
            else:
                self.computer._page.fill(selector, text)
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            # Take screenshot
            screenshot_base64 = self.computer.screenshot()
            saved_path = save_screenshot(screenshot_base64)
            
            return {
                "status": "success",
                "message": f"Typed text into {selector}",
                "selector": selector,
                "text": text,
                "elapsed_ms": elapsed_ms,
                "screenshot": f"data:image/png;base64,{screenshot_base64}",
                "saved_path": saved_path,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            log_error(f"Error typing text into {selector}: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def scroll_page(self, amount: int = 300, smooth: bool = True, 
                   humanlike: bool = False, important_action: bool = False) -> Dict[str, Any]:
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
        if not self.computer or not hasattr(self.computer, "_page"):
            return {"status": "error", "message": "Computer not initialized"}
        
        try:
            # Log the action
            log_action("scroll_page", f"amount={amount}, smooth={smooth}, humanlike={humanlike}")
            
            if humanlike:
                # Perform human-like scrolling with multiple random steps
                total_scrolled = 0
                steps = random.randint(3, 7) if abs(amount) > 300 else random.randint(1, 3)
                step_size = amount / steps
                
                for i in range(steps):
                    # Create a slightly random step size for natural feel
                    if i < steps - 1:  # Not the last step
                        actual_step = step_size * random.uniform(0.8, 1.2)
                    else:  # Last step - ensure we reach the desired total
                        actual_step = amount - total_scrolled
                    
                    self.computer._page.evaluate(f"""
                        window.scrollBy({{ 
                            top: {actual_step}, 
                            left: 0, 
                            behavior: '{"smooth" if smooth else "auto"}' 
                        }});
                    """)
                    
                    total_scrolled += actual_step
                    time.sleep(random.uniform(0.1, 0.4))  # Random pause between scrolls
            else:
                # Perform a single scroll
                self.computer._page.evaluate(f"""
                    window.scrollBy({{ 
                        top: {amount}, 
                        left: 0, 
                        behavior: '{"smooth" if smooth else "auto"}' 
                    }});
                """)
                
                # Wait for smooth scroll to complete
                if smooth:
                    time.sleep(0.5)
            
            # Take screenshot
            screenshot_base64 = self.computer.screenshot()
            saved_path = save_screenshot(screenshot_base64)
            
            return {
                "status": "success",
                "message": f"Scrolled page by {amount} pixels",
                "amount": amount,
                "humanlike": humanlike,
                "screenshot": f"data:image/png;base64,{screenshot_base64}",
                "saved_path": saved_path,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            log_error(f"Error scrolling page: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def wait_for_element(self, selector: str, timeout_ms: int = 30000, 
                       state: str = "visible") -> Dict[str, Any]:
        """
        Wait for an element to appear in the DOM.
        
        Args:
            selector: CSS selector for the element
            timeout_ms: Maximum time to wait in milliseconds
            state: Element state to wait for ("attached", "detached", "visible", "hidden")
        
        Returns:
            dict: Wait result
        """
        if not self.computer or not hasattr(self.computer, "_page"):
            return {"status": "error", "message": "Computer not initialized"}
        
        try:
            # Log the action
            log_action("wait_for_element", f"selector={selector}, state={state}, timeout={timeout_ms}ms")
            
            # Wait for element
            start_time = time.time()
            element = self.computer._page.wait_for_selector(
                selector, state=state, timeout=timeout_ms
            )
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            # Check if element was found
            if element:
                # Take screenshot
                screenshot_base64 = self.computer.screenshot()
                saved_path = save_screenshot(screenshot_base64)
                
                return {
                    "status": "success",
                    "message": f"Found element: {selector} (state: {state})",
                    "selector": selector,
                    "elapsed_ms": elapsed_ms,
                    "screenshot": f"data:image/png;base64,{screenshot_base64}",
                    "saved_path": saved_path,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "status": "error",
                    "message": f"Element not found: {selector} (state: {state})",
                    "elapsed_ms": elapsed_ms,
                    "timestamp": datetime.now().isoformat()
                }
        except Exception as e:
            log_error(f"Error waiting for element {selector}: {str(e)}")
            return {"status": "error", "message": str(e)}
