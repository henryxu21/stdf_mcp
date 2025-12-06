"""
MCP Tools Registration and Management.

This module registers all available MCP tools with the server and provides
a centralized registry for tool discovery and execution.

Features:
- All 6 metadata extraction tools for User Story 1
- Intel CPU little-endian constraint enforcement across all tools
- Centralized error handling and validation
- Tool versioning and metadata tracking
"""

from typing import Dict, Any, Callable, List, Optional
import inspect
from functools import wraps

# Import all metadata tools
from .metadata.file_overview import extract_file_overview
from .metadata.test_configuration import extract_test_configuration
from .metadata.yield_summary import extract_yield_summary
from .metadata.facility_details import extract_facility_details
from .metadata.program_metadata import extract_program_metadata
from .metadata.test_parameters import extract_test_parameters

# Import yield analysis tools
from .yield_analysis.per_unit_yield import extract_per_unit_yield

# Tool registry
REGISTERED_TOOLS: Dict[str, Dict[str, Any]] = {}


def register_tool(name: str, func: Callable, description: str, category: str = "metadata"):
    """
    Register a tool with the MCP server.

    Args:
        name: Tool name (must be unique)
        func: Tool function to execute
        description: Tool description for documentation
        category: Tool category for organization
    """
    REGISTERED_TOOLS[name] = {
        "function": func,
        "description": description,
        "category": category,
        "signature": inspect.signature(func),
        "module": func.__module__,
        "version": "1.0.0"
    }


def get_tool(name: str) -> Optional[Dict[str, Any]]:
    """
    Get a registered tool by name.

    Args:
        name: Tool name

    Returns:
        Tool information dict or None if not found
    """
    return REGISTERED_TOOLS.get(name)


def list_tools(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List all registered tools, optionally filtered by category.

    Args:
        category: Optional category filter

    Returns:
        List of tool information dicts
    """
    tools = []
    for name, tool_info in REGISTERED_TOOLS.items():
        if category is None or tool_info["category"] == category:
            tools.append({
                "name": name,
                **tool_info
            })
    return tools


def execute_tool(name: str, *args, **kwargs) -> Any:
    """
    Execute a registered tool.

    Args:
        name: Tool name
        *args: Positional arguments to pass to tool
        **kwargs: Keyword arguments to pass to tool

    Returns:
        Tool execution result

    Raises:
        ValueError: If tool is not registered
        Exception: Tool execution errors
    """
    tool_info = get_tool(name)
    if not tool_info:
        raise ValueError(f"Tool '{name}' is not registered")

    try:
        return tool_info["function"](*args, **kwargs)
    except Exception as e:
        # Add tool context to error
        raise Exception(f"Error executing tool '{name}': {str(e)}") from e


# Error handling decorator for Intel CPU constraint enforcement
def intel_cpu_constraint(func):
    """
    Decorator to enforce Intel CPU little-endian constraint across all tools.

    This decorator wraps tool functions to ensure consistent error handling
    and constraint enforcement.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Ensure Intel CPU constraint errors are properly propagated
            if "Intel CPU" in str(e) or "little-endian" in str(e) or "big-endian" in str(e):
                raise
            else:
                # Re-raise with tool context
                raise Exception(f"Tool execution error: {str(e)}") from e
    return wrapper


# Register all User Story 1 metadata tools
def register_metadata_tools():
    """Register all 6 metadata extraction tools for User Story 1."""

    register_tool(
        name="extract_file_overview",
        func=intel_cpu_constraint(extract_file_overview),
        description="Extract quick file assessment with key identifiers and summary statistics",
        category="metadata"
    )

    register_tool(
        name="extract_test_configuration",
        func=intel_cpu_constraint(extract_test_configuration),
        description="Extract test conditions, hardware configuration, and site descriptions",
        category="metadata"
    )

    register_tool(
        name="extract_yield_summary",
        func=intel_cpu_constraint(extract_yield_summary),
        description="Extract part count records, retest information, and computed statistics",
        category="metadata"
    )

    register_tool(
        name="extract_facility_details",
        func=intel_cpu_constraint(extract_facility_details),
        description="Extract location information, process information, engineering context, and timing",
        category="metadata"
    )

    register_tool(
        name="extract_program_metadata",
        func=intel_cpu_constraint(extract_program_metadata),
        description="Extract program identification, specifications, tester software, and user context",
        category="metadata"
    )

    register_tool(
        name="extract_test_parameters",
        func=intel_cpu_constraint(extract_test_parameters),
        description="Extract test parameters with filtering options (with_limits, without_limits, all)",
        category="metadata"
    )


def register_yield_analysis_tools():
    """Register yield analysis tools."""

    register_tool(
        name="extract_per_unit_yield",
        func=extract_per_unit_yield,
        description="Extract per-unit pass/fail yield data from STDF file to CSV with PART_ID, PorF, HW Bin, SW Bin columns",
        category="yield_analysis"
    )


# Auto-register tools when module is imported
register_metadata_tools()
register_yield_analysis_tools()


# Export public interface
__all__ = [
    "REGISTERED_TOOLS",
    "register_tool",
    "get_tool",
    "list_tools",
    "execute_tool",
    "register_metadata_tools",
    "register_yield_analysis_tools",
    "intel_cpu_constraint",
    "extract_per_unit_yield"
]


# Tool registry summary for debugging
def get_tool_registry_summary() -> Dict[str, Any]:
    """
    Get a summary of the tool registry for debugging and validation.

    Returns:
        Dict with registry statistics and tool list
    """
    categories = {}
    for tool_info in REGISTERED_TOOLS.values():
        category = tool_info["category"]
        categories[category] = categories.get(category, 0) + 1

    return {
        "total_tools": len(REGISTERED_TOOLS),
        "categories": categories,
        "tool_names": list(REGISTERED_TOOLS.keys()),
        "metadata_tools_count": categories.get("metadata", 0),
        "intel_cpu_constraint_enforced": True
    }


if __name__ == "__main__":
    # Print tool registry summary for debugging
    import json
    summary = get_tool_registry_summary()
    print("Tool Registry Summary:")
    print(json.dumps(summary, indent=2))

    print("\nRegistered Tools:")
    for tool in list_tools():
        print(f"- {tool['name']}: {tool['description']}")