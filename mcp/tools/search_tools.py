#!/usr/bin/env python
"""
Search Tools for Claude Desktop MCP Server

This module provides search-related tools for the Claude Desktop MCP server.
It leverages the existing search functionality from the CUA codebase.
"""

import os
import sys
import time
from typing import Dict, List, Optional, Any

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import from existing codebase
from computers import SearchEngineManager, SearchEngineParams
from computers.search import perform_resilient_search, search_weather
from utils import log_info, log_debug, log_error, save_screenshot


class SearchTools:
    """
    Tools for performing searches with resilient fallback.
    """
    
    def __init__(self, computer=None):
        """
        Initialize search tools with a computer instance.
        
        Args:
            computer: Computer instance for performing searches
        """
        self.computer = computer
        self.search_manager = SearchEngineManager()
        log_info(f"Initialized SearchTools with {len(self.search_manager.engines)} engines")
    
    def set_computer(self, computer):
        """
        Set the computer instance for performing searches.
        
        Args:
            computer: Computer instance for performing searches
        """
        self.computer = computer
    
    def resilient_search(self, query: str, params: Optional[Dict[str, Any]] = None,
                        humanlike: bool = True, take_screenshots: bool = True) -> Dict[str, Any]:
        """
        Perform a search using multiple search engines with fallback.
        
        Args:
            query: Search query
            params: Search parameters (language, region, etc.)
            humanlike: Whether to simulate human-like behavior
            take_screenshots: Whether to capture screenshots
        
        Returns:
            dict: Search results
        """
        if not self.computer:
            return {"status": "error", "message": "Computer not initialized"}
        
        try:
            # Prepare search parameters
            search_params = None
            if params:
                search_params = SearchEngineParams(
                    language_code=params.get("language"),
                    country_code=params.get("country"),
                    safe_search=params.get("safe_search"),
                    time_period=params.get("time_period"),
                    content_type=params.get("content_type"),
                    site_search=params.get("site_search"),
                    results_count=params.get("results_count")
                )
            
            # Perform the search
            log_info(f"Performing resilient search for: {query}")
            results = perform_resilient_search(
                self.computer,
                query,
                manager=self.search_manager,
                humanlike=humanlike,
                extract_structured_data=True,
                take_screenshots=take_screenshots,
                search_params=search_params
            )
            
            # Process results
            if hasattr(results, 'organic_results'):
                # Process structured results
                return {
                    "status": "success",
                    "query": query,
                    "engine_used": results.engine_name,
                    "total_results": results.total_results_count,
                    "search_time": results.search_time,
                    "organic_results": [
                        {
                            "title": result.title,
                            "url": result.url,
                            "snippet": result.snippet,
                            "position": result.position
                        } for result in results.organic_results[:10]
                    ],
                    "featured_snippet": {
                        "title": results.featured_snippet.title,
                        "content": results.featured_snippet.content,
                        "source_url": results.featured_snippet.source_url
                    } if results.featured_snippet else None,
                    "related_searches": results.related_searches[:5] if results.related_searches else []
                }
            else:
                # Handle boolean result
                return {
                    "status": "success" if results else "error",
                    "query": query,
                    "message": "Search completed successfully" if results else "Search failed"
                }
        except Exception as e:
            log_error(f"Error performing search: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def search_weather(self, location: str, language: Optional[str] = None,
                     country: Optional[str] = None, humanlike: bool = True) -> Dict[str, Any]:
        """
        Search for weather information.
        
        Args:
            location: Location to search weather for
            language: Language code for search results
            country: Country code for search results
            humanlike: Whether to simulate human-like behavior
        
        Returns:
            dict: Weather search results
        """
        if not self.computer:
            return {"status": "error", "message": "Computer not initialized"}
        
        try:
            # Perform weather search
            log_info(f"Searching for weather in {location}")
            results = search_weather(
                self.computer,
                location,
                humanlike=humanlike,
                extract_structured_data=True,
                language=language,
                country=country
            )
            
            # Process results
            if hasattr(results, 'organic_results'):
                # Process structured results
                weather_info = None
                
                # Look for weather data in featured snippet
                if results.featured_snippet:
                    weather_info = {
                        "title": results.featured_snippet.title,
                        "content": results.featured_snippet.content,
                        "source": results.featured_snippet.source_url
                    }
                
                # If no featured snippet, try to find weather in organic results
                if not weather_info:
                    for result in results.organic_results:
                        if ("weather" in result.title.lower() or 
                            "forecast" in result.title.lower() or
                            "temperature" in result.title.lower()):
                            weather_info = {
                                "title": result.title,
                                "content": result.snippet,
                                "source": result.url
                            }
                            break
                
                return {
                    "status": "success",
                    "location": location,
                    "engine_used": results.engine_name,
                    "weather_info": weather_info,
                    "organic_results": [
                        {
                            "title": result.title,
                            "url": result.url,
                            "snippet": result.snippet
                        } for result in results.organic_results[:5]
                    ]
                }
            else:
                # Handle boolean result
                return {
                    "status": "success" if results else "error",
                    "location": location,
                    "message": "Weather search completed successfully" if results else "Weather search failed"
                }
        except Exception as e:
            log_error(f"Error searching for weather: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def get_available_engines(self) -> Dict[str, Any]:
        """
        Get a list of available search engines.
        
        Returns:
            dict: Available search engines
        """
        try:
            engines = self.search_manager.engines
            return {
                "status": "success",
                "engines": [{
                    "name": engine.name,
                    "base_url": engine.base_url,
                    "success_count": self.search_manager.success_counts.get(engine.name, 0),
                    "failure_count": self.search_manager.failure_counts.get(engine.name, 0)
                } for engine in engines]
            }
        except Exception as e:
            log_error(f"Error getting available engines: {str(e)}")
            return {"status": "error", "message": str(e)}
