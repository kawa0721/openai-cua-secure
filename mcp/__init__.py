"""
Claude Desktop MCP (Model Context Protocol) Server

This package provides a Model Context Protocol (MCP) server implementation 
that allows Claude Desktop to interact with the CUA (Computer Using Agent) functionality.
"""

# Required imports
from mcp.server import Server
from mcp.bridge import CUABridge

# Version
__version__ = "0.1.0"
