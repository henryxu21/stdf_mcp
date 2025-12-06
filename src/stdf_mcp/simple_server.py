"""
Simple STDF MCP Server for User Story 1 - Metadata Extraction Tools.

This server exposes the 6 implemented metadata extraction tools via MCP protocol.
"""

import asyncio
import json
import logging
import sys
from typing import Any, Dict, List

# MCP SDK imports
from mcp.server.lowlevel import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, Resource

# Import our actual implemented tools
from stdf_mcp.tools.metadata.file_overview import extract_file_overview
from stdf_mcp.tools.metadata.test_configuration import (
    extract_test_configuration,
)
from stdf_mcp.tools.metadata.yield_summary import extract_yield_summary
from stdf_mcp.tools.metadata.facility_details import extract_facility_details
from stdf_mcp.tools.metadata.program_metadata import extract_program_metadata
from stdf_mcp.tools.metadata.test_parameters import extract_test_parameters

# Import record extraction tools (User Story 1 - Feature 002)
from stdf_mcp.tools.record_extraction.far_extractor import extract_far_record
from stdf_mcp.tools.record_extraction.mir_extractor import extract_mir_record
from stdf_mcp.tools.record_extraction.hbr_extractor import extract_hbr_records
from stdf_mcp.tools.record_extraction.sbr_extractor import extract_sbr_records
from stdf_mcp.tools.record_extraction.pcr_extractor import extract_pcr_records
from stdf_mcp.tools.record_extraction.sdr_extractor import extract_sdr_records
from stdf_mcp.tools.record_extraction.mrr_extractor import extract_mrr_record

# Import test parameter summary tool (Feature 003 - US1)
from stdf_mcp.tools.test_summary.parameter_summary import (
    extract_test_parameter_summary,
)

# Import filtered data extraction tool (Feature 005)
from stdf_mcp.tools.filtered_data.tool import extract_filtered_data

# Import test time extraction tool (Feature 008)
from stdf_mcp.tools.test_time.tool import extract_test_time

# Import yield analysis tool (Feature 009)
from stdf_mcp.tools.yield_analysis.per_unit_yield import extract_per_unit_yield

# Configure safe logging for MCP server environment
import os


# Module-level cache for tools (Feature 010 - contract testing)
_TOOLS_CACHE = None


def get_tool_by_name(tool_name: str) -> Tool:
    """Get tool definition by name for contract testing.

    Uses a module-level cache. Populates cache on first call by creating
    a server instance and manually calling list_tools handler.

    Args:
        tool_name: Name of the tool to retrieve

    Returns:
        Tool object with input/output schemas

    Raises:
        ValueError: If tool not found
    """
    global _TOOLS_CACHE

    # Lazy initialize cache on first call
    if _TOOLS_CACHE is None or len(_TOOLS_CACHE) == 0:
        # Create server instance to get tools list
        server_instance = SimpleSTDFMCPServer()
        # Trigger list_tools by accessing the async handler directly
        # Since we can't call async from sync context, we manually build tools list
        # This is a copy of the tools list from list_tools() handler
        _TOOLS_CACHE = _build_tools_list()

    # Find tool in cached list
    for tool in _TOOLS_CACHE:
        if tool.name == tool_name:
            return tool

    raise ValueError(
        f"Tool '{tool_name}' not found in {len(_TOOLS_CACHE)} tools"
    )


def _build_tools_list() -> list:
    """Build tools list for contract testing.

    This duplicates part of the list_tools() logic to make tools accessible
    for synchronous contract tests without running async server.

    Returns:
        List of Tool objects
    """
    # Import here to avoid circular dependency during module load
    return []  # Will be populated after class definition


log_handlers = [logging.StreamHandler()]  # Always have console logging

# Create a consistent formatter for all handlers
log_formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Set formatter on console handler
log_handlers[0].setFormatter(log_formatter)

# Add file logging only if we can write to the directory
try:
    log_file_path = os.path.join(
        os.path.expanduser("~"), "Library", "Logs", "mcp_server_debug.log"
    )
    # Ensure the directory exists
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
    # Test if we can write to the file
    test_file = open(log_file_path, "a")
    test_file.close()

    # Create file handler with formatter
    file_handler = logging.FileHandler(log_file_path)
    file_handler.setFormatter(log_formatter)
    log_handlers.append(file_handler)
except (PermissionError, OSError):
    # If file logging fails, just use console logging
    pass

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=log_handlers,
)

# Get the root logger and add our handlers explicitly
logger = logging.getLogger(__name__)
# Ensure the named logger gets the same handlers as the root logger
for handler in log_handlers:
    logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


def write_to_file(filepath: str, content: str, mode: str = "w") -> bool:
    """
    Writes the given string content to a specified file path.

    The file will be created if it does not exist.

    Args:
        filepath (str): The path to the file to write to (e.g., 'output.txt').
        content (str): The string content to write into the file.
        mode (str): The file opening mode.
                    'w' (write): Overwrites the file if it exists. (Default)
                    'a' (append): Adds content to the end of the file.

    Returns:
        bool: True if the write operation was successful, False otherwise.
    """
    if not isinstance(filepath, str) or not filepath:
        print("Error: Filepath must be a non-empty string.")
        return False

    if mode not in ("w", "a"):
        print(
            f"Error: Invalid mode '{mode}'. Use 'w' (write) or 'a' (append)."
        )
        return False

    try:
        # Use 'with' statement for automatic file closing, even if errors occur
        with open(filepath, mode, encoding="utf-8") as f:
            f.write(content)
        print(f"Successfully wrote content to: {filepath}")
        return True
    except IOError as e:
        # Catch errors related to file operations (permissions, path issues, etc.)
        print(f"IOError: Could not write to file {filepath}. Details: {e}")
        return False
    except Exception as e:
        # Catch any other unexpected errors
        print(f"An unexpected error occurred: {e}")
        return False


class SimpleSTDFMCPServer:
    """
    Simple MCP Server for STDF metadata and record extraction tools.

    Exposes metadata extraction tools (User Story 1):
    1. extract_file_overview
    2. extract_test_configuration
    3. extract_yield_summary
    4. extract_facility_details
    5. extract_program_metadata
    6. extract_test_parameters

    Exposes record extraction tools (Feature 002 - US1):
    7. extract_far_record
    8. extract_mir_record
    9. extract_hbr_records
    10. extract_sbr_records
    11. extract_pcr_records
    12. extract_sdr_records
    13. extract_mrr_record

    Exposes test parameter summary tools (Feature 003 - US1):
    14. extract_test_parameter_summary (supports test suite filtering)

    Exposes filtered data extraction tools (Feature 005):
    15. extract_filtered_data (supports test suite filtering)

    Exposes test time extraction tools (Feature 008):
    16. extract_test_time (extracts PRR.TEST_T with statistics and site filtering)

    Exposes yield analysis tools (Feature 009):
    17. extract_per_unit_yield (extracts per-unit P/F yield data to CSV)

    Total: 17 tools (consolidated API with test suite and site filtering support)
    """

    def __init__(self):
        """Initialize Simple STDF MCP Server."""
        self.server = Server("stdf-v4-analyzer")
        self._setup_tools()
        self._setup_resources()

    def _setup_resources(self) -> None:
        """Setup MCP resources."""

        @self.server.list_resources()
        async def list_resources() -> List[Resource]:
            """List available STDF resources."""
            logger.info("📥 JSON REQUEST: list_resources (no params)")

            resources = [
                Resource(
                    uri="stdf://parser/config",
                    name="STDF Parser Configuration",
                    mimeType="application/json",
                    description="Current parser configuration settings",
                ),
                Resource(
                    uri="stdf://tools/list",
                    name="Available STDF Tools",
                    mimeType="application/json",
                    description="List of all available STDF analysis tools",
                ),
            ]

            logger.info(
                f"📤 JSON RESPONSE: list_resources -> {len(resources)} resources"
            )
            logger.debug(
                f"📤 JSON RESPONSE DETAIL: {[r.uri for r in resources]}"
            )

            return resources

        @self.server.read_resource()
        async def read_resource(uri: str) -> str:
            """Read STDF resource content."""
            logger.info(f"📥 JSON REQUEST: resources/read -> uri: {uri}")

            if uri == "stdf://parser/config":
                config = {
                    "server_name": "stdf-v4-analyzer",
                    "server_version": "1.0.0",
                    "intel_cpu_constraint": True,
                    "stdf_v4_only": True,
                    "package_test_only": True,
                }
                result = json.dumps(config, indent=2)
                logger.info(
                    f"📤 JSON RESPONSE: resources/read -> config ({len(result)} chars)"
                )
                return result

            elif uri == "stdf://tools/list":
                tools = {
                    "metadata_tools": [
                        "extract_file_overview_tool",
                        "extract_test_configuration_tool",
                        "extract_yield_summary_tool",
                        "extract_facility_details_tool",
                        "extract_program_metadata_tool",
                        "extract_test_parameters_tool",
                    ],
                    "record_extraction_tools": [
                        "extract_far_record_tool",
                        "extract_mir_record_tool",
                        "extract_hbr_records_tool",
                        "extract_sbr_records_tool",
                        "extract_pcr_records_tool",
                        "extract_sdr_records_tool",
                        "extract_mrr_record_tool",
                    ],
                    "test_summary_tools": [
                        "extract_test_parameter_summary_tool"
                    ],
                    "filtered_data_tools": ["extract_filtered_data_tool"],
                    "test_time_tools": ["extract_test_time_tool"],
                    "yield_analysis_tools": ["extract_per_unit_yield_tool"],
                    "tool_count": 17,
                    "description": "STDF metadata, record extraction, test summary, filtered data, test time analysis, and yield analysis tools (with test suite and site filtering support)",
                }
                result = json.dumps(tools, indent=2)
                logger.info(
                    f"📤 JSON RESPONSE: resources/read -> tools list ({len(result)} chars)"
                )
                return result

            else:
                error_msg = f"Unknown resource: {uri}"
                logger.info(
                    f"📤 JSON RESPONSE: resources/read -> ERROR: {error_msg}"
                )
                raise ValueError(error_msg)

        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List available STDF tools for MCP clients."""
            logger.info("📥 JSON REQUEST: tools/list (no params)")

            tools = [
                Tool(
                    name="extract_file_overview_tool",
                    description="Extract quick file assessment with key identifiers and summary statistics",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Absolute path to STDF-V4 package test file",
                            }
                        },
                        "required": ["file_path"],
                    },
                    outputSchema={
                        "type": "object",
                        "properties": {
                            "file_info": {
                                "type": "object",
                                "properties": {
                                    "file_path": {"type": "string"},
                                    "file_size": {"type": "integer"},
                                    "stdf_version": {"type": "string"},
                                    "cpu_type": {"type": "string"},
                                    "creation_time": {"type": "string"},
                                    "modification_time": {"type": "string"},
                                },
                                "description": "Basic file information and format details",
                            },
                            "key_identifiers": {
                                "type": "object",
                                "properties": {
                                    "lot_id": {"type": ["string", "null"]},
                                    "part_typ": {"type": ["string", "null"]},
                                    "wafer_id": {"type": ["string", "null"]},
                                    "device_type": {
                                        "type": ["string", "null"]
                                    },
                                    "test_program": {
                                        "type": ["string", "null"]
                                    },
                                    "facility_id": {
                                        "type": ["string", "null"]
                                    },
                                },
                                "description": "Key identifiers extracted from MIR record",
                            },
                            "summary_statistics": {
                                "type": "object",
                                "properties": {
                                    "total_records": {"type": "integer"},
                                    "total_test_time": {"type": "number"},
                                    "parts_tested": {"type": "integer"},
                                    "total_test_sites": {"type": "integer"},
                                    "overall_yield": {"type": "number"},
                                },
                                "description": "High-level test statistics and counts",
                            },
                            "_metadata": {
                                "type": "object",
                                "description": "Tool execution metadata including timing and version",
                            },
                        },
                        "required": [
                            "file_info",
                            "key_identifiers",
                            "summary_statistics",
                            "_metadata",
                        ],
                    },
                ),
                Tool(
                    name="extract_test_configuration_tool",
                    description="Extract test conditions, hardware configuration, and site descriptions",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Absolute path to STDF-V4 package test file",
                            }
                        },
                        "required": ["file_path"],
                    },
                    outputSchema={
                        "type": "object",
                        "properties": {
                            "test_conditions": {
                                "type": "object",
                                "properties": {
                                    "tst_temp": {"type": ["number", "null"]},
                                    "mode_cod": {"type": ["string", "null"]},
                                    "setup_id": {"type": ["string", "null"]},
                                    "flow_id": {"type": ["string", "null"]},
                                },
                                "description": "Test environment conditions and parameters",
                            },
                            "hardware_configuration": {
                                "type": "object",
                                "properties": {
                                    "serl_num": {"type": ["string", "null"]},
                                    "tstr_typ": {"type": ["string", "null"]},
                                    "exec_typ": {"type": ["string", "null"]},
                                    "exec_ver": {"type": ["string", "null"]},
                                },
                                "description": "Hardware and tester configuration details",
                            },
                            "site_descriptions": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "site_cnt": {"type": "integer"},
                                        "site_num": {
                                            "type": "array",
                                            "items": {"type": "integer"},
                                        },
                                        "hand_typ": {
                                            "type": ["string", "null"]
                                        },
                                        "hand_id": {
                                            "type": ["string", "null"]
                                        },
                                        "load_typ": {
                                            "type": ["string", "null"]
                                        },
                                        "load_id": {
                                            "type": ["string", "null"]
                                        },
                                        "dib_typ": {
                                            "type": ["string", "null"]
                                        },
                                        "dib_id": {"type": ["string", "null"]},
                                    },
                                },
                                "description": "Test site configuration and handler details",
                            },
                            "_metadata": {
                                "type": "object",
                                "description": "Tool execution metadata including timing and version",
                            },
                        },
                        "required": [
                            "test_conditions",
                            "hardware_configuration",
                            "site_descriptions",
                            "_metadata",
                        ],
                    },
                ),
                Tool(
                    name="extract_yield_summary_tool",
                    description="Extract part count records, retest information, and computed statistics",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Absolute path to STDF-V4 package test file",
                            }
                        },
                        "required": ["file_path"],
                    },
                    outputSchema={
                        "type": "object",
                        "properties": {
                            "part_count_records": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "head_num": {"type": "integer"},
                                        "site_num": {"type": "integer"},
                                        "part_cnt": {"type": "integer"},
                                        "rtst_cnt": {"type": "integer"},
                                        "abrt_cnt": {"type": "integer"},
                                        "good_cnt": {"type": "integer"},
                                        "func_cnt": {"type": "integer"},
                                        "yield_percentage": {"type": "number"},
                                    },
                                },
                                "description": "Part count records from PCR records by site",
                            },
                            "computed_statistics": {
                                "type": "object",
                                "properties": {
                                    "overall_yield": {"type": "number"},
                                    "total_parts_tested": {"type": "integer"},
                                    "total_good_parts": {"type": "integer"},
                                    "total_retest_parts": {"type": "integer"},
                                    "total_abort_parts": {"type": "integer"},
                                    "site_count": {"type": "integer"},
                                },
                                "description": "Computed yield statistics across all sites",
                            },
                            "_metadata": {
                                "type": "object",
                                "description": "Tool execution metadata including timing and version",
                            },
                        },
                        "required": [
                            "part_count_records",
                            "computed_statistics",
                            "_metadata",
                        ],
                    },
                ),
                Tool(
                    name="extract_facility_details_tool",
                    description="Extract location information, process information, engineering context, and timing",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Absolute path to STDF-V4 package test file",
                            }
                        },
                        "required": ["file_path"],
                    },
                    outputSchema={
                        "type": "object",
                        "properties": {
                            "location_information": {
                                "type": "object",
                                "properties": {
                                    "facil_id": {"type": ["string", "null"]},
                                    "floor_id": {"type": ["string", "null"]},
                                    "proc_id": {"type": ["string", "null"]},
                                    "node_nam": {"type": ["string", "null"]},
                                },
                                "description": "Physical location and facility identification",
                            },
                            "process_information": {
                                "type": "object",
                                "properties": {
                                    "oper_nam": {"type": ["string", "null"]},
                                    "famly_id": {"type": ["string", "null"]},
                                    "sblot_id": {"type": ["string", "null"]},
                                    "oper_freq": {"type": ["number", "null"]},
                                },
                                "description": "Manufacturing process and operation details",
                            },
                            "engineering_context": {
                                "type": "object",
                                "properties": {
                                    "eng_id": {"type": ["string", "null"]},
                                    "rom_cod": {"type": ["string", "null"]},
                                    "dsgn_rev": {"type": ["string", "null"]},
                                    "tst_cod": {"type": ["string", "null"]},
                                },
                                "description": "Engineering and design context information",
                            },
                            "timing_information": {
                                "type": "object",
                                "properties": {
                                    "setup_t": {"type": ["number", "null"]},
                                    "start_t": {"type": ["number", "null"]},
                                    "finish_t": {"type": ["number", "null"]},
                                    "test_duration": {
                                        "type": ["number", "null"]
                                    },
                                },
                                "description": "Test timing and duration information",
                            },
                            "_metadata": {
                                "type": "object",
                                "description": "Tool execution metadata including timing and version",
                            },
                        },
                        "required": [
                            "location_information",
                            "process_information",
                            "engineering_context",
                            "timing_information",
                            "_metadata",
                        ],
                    },
                ),
                Tool(
                    name="extract_program_metadata_tool",
                    description="Extract program identification, specifications, tester software, and user context",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Absolute path to STDF-V4 package test file",
                            }
                        },
                        "required": ["file_path"],
                    },
                    outputSchema={
                        "type": "object",
                        "properties": {
                            "program_identification": {
                                "type": "object",
                                "properties": {
                                    "job_nam": {"type": ["string", "null"]},
                                    "job_rev": {"type": ["string", "null"]},
                                    "spec_nam": {"type": ["string", "null"]},
                                    "spec_ver": {"type": ["string", "null"]},
                                },
                                "description": "Test program identification and version information",
                            },
                            "specifications": {
                                "type": "object",
                                "properties": {
                                    "aux_file": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "pkg_typ": {"type": ["string", "null"]},
                                    "famly_id": {"type": ["string", "null"]},
                                    "date_cod": {"type": ["string", "null"]},
                                },
                                "description": "Program specifications and auxiliary files",
                            },
                            "tester_software": {
                                "type": "object",
                                "properties": {
                                    "exec_typ": {"type": ["string", "null"]},
                                    "exec_ver": {"type": ["string", "null"]},
                                    "tstr_typ": {"type": ["string", "null"]},
                                    "cmod_cod": {"type": ["string", "null"]},
                                },
                                "description": "Tester software and execution environment",
                            },
                            "user_context": {
                                "type": "object",
                                "properties": {
                                    "user_nam": {"type": ["string", "null"]},
                                    "user_txt": {"type": ["string", "null"]},
                                    "supr_nam": {"type": ["string", "null"]},
                                    "oper_nam": {"type": ["string", "null"]},
                                },
                                "description": "User and operator context information",
                            },
                            "_metadata": {
                                "type": "object",
                                "description": "Tool execution metadata including timing and version",
                            },
                        },
                        "required": [
                            "program_identification",
                            "specifications",
                            "tester_software",
                            "user_context",
                            "_metadata",
                        ],
                    },
                ),
                Tool(
                    name="extract_test_parameters_tool",
                    description="Extract test parameters with filtering options (with_limits, without_limits, all)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Absolute path to STDF-V4 package test file",
                            },
                            "filter_option": {
                                "type": "string",
                                "description": "Filter option for parameters",
                                "enum": [
                                    "all_parameters",
                                    "with_limits_only",
                                    "without_limits_only",
                                ],
                                "default": "all_parameters",
                            },
                        },
                        "required": ["file_path"],
                    },
                    outputSchema={
                        "type": "object",
                        "properties": {
                            "parameters_with_limits": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "test_number": {"type": "integer"},
                                        "test_name": {
                                            "type": ["string", "null"]
                                        },
                                        "units": {"type": ["string", "null"]},
                                        "low_limit": {
                                            "type": ["number", "null"]
                                        },
                                        "high_limit": {
                                            "type": ["number", "null"]
                                        },
                                        "test_type": {"type": "string"},
                                    },
                                },
                                "description": "Parameters that have defined limits (PTR records)",
                            },
                            "parameters_without_limits": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "test_number": {"type": "integer"},
                                        "test_name": {
                                            "type": ["string", "null"]
                                        },
                                        "test_type": {"type": "string"},
                                        "functional_details": {
                                            "type": ["object", "null"]
                                        },
                                    },
                                },
                                "description": "Parameters without limits (FTR records)",
                            },
                            "total_parameter_count": {
                                "type": "integer",
                                "description": "Total number of unique test parameters found",
                            },
                            "parametric_test_count": {
                                "type": "integer",
                                "description": "Number of parametric tests (PTR records)",
                            },
                            "functional_test_count": {
                                "type": "integer",
                                "description": "Number of functional tests (FTR records)",
                            },
                            "filter_option": {
                                "type": "string",
                                "description": "Applied filter option",
                            },
                            "_metadata": {
                                "type": "object",
                                "description": "Tool execution metadata including timing and version",
                            },
                        },
                        "required": [
                            "parameters_with_limits",
                            "parameters_without_limits",
                            "total_parameter_count",
                            "parametric_test_count",
                            "functional_test_count",
                            "filter_option",
                            "_metadata",
                        ],
                    },
                ),
                # Record Extraction Tools (Feature 002 - US1)
                Tool(
                    name="extract_far_record_tool",
                    description="Extract FAR (File Attributes Record) from STDF file - contains CPU type and STDF version",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Absolute path to STDF file",
                            }
                        },
                        "required": ["file_path"],
                    },
                ),
                Tool(
                    name="extract_mir_record_tool",
                    description="Extract MIR (Master Information Record) with all 38 fields including lot ID, part type, test configuration",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Absolute path to STDF file",
                            }
                        },
                        "required": ["file_path"],
                    },
                ),
                Tool(
                    name="extract_hbr_records_tool",
                    description="Extract all HBR (Hardware Bin Records) - one per hardware bin with counts and pass/fail status",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Absolute path to STDF file",
                            }
                        },
                        "required": ["file_path"],
                    },
                ),
                Tool(
                    name="extract_sbr_records_tool",
                    description="Extract all SBR (Software Bin Records) - one per software bin with counts and pass/fail status",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Absolute path to STDF file",
                            }
                        },
                        "required": ["file_path"],
                    },
                ),
                Tool(
                    name="extract_pcr_records_tool",
                    description="Extract all PCR (Part Count Records) - one per test site with part counts and yield data",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Absolute path to STDF file",
                            }
                        },
                        "required": ["file_path"],
                    },
                ),
                Tool(
                    name="extract_sdr_records_tool",
                    description="Extract all SDR (Site Description Records) - test site configuration with handler, load board, and DIB details",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Absolute path to STDF file",
                            }
                        },
                        "required": ["file_path"],
                    },
                ),
                Tool(
                    name="extract_mrr_record_tool",
                    description="Extract MRR (Master Results Record) - lot disposition and test completion summary",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Absolute path to STDF file",
                            }
                        },
                        "required": ["file_path"],
                    },
                ),
                # Test Parameter Summary Tool (Feature 003 - US1 & US2, Feature 004 - US1, Feature 010 - CSV Export)
                Tool(
                    name="extract_test_parameter_summary_tool",
                    description="Extract test parameter summary combining TSR (Test Synopsis Record) statistics with PTR (Parametric Test Record) limits. Supports searching by test_name (exact or regex), test_num (single number), test_num range, or test_suite_name (simple or qualified). Optionally exports results to CSV file for analysis in Excel or pandas. IMPORTANT: When export_csv=true AND CSV export succeeds, JSON summaries are omitted to save LLM tokens (data is in CSV file). If CSV export fails, summaries are included for graceful degradation. Examples: (1) Exact name: 'VDD_CORE' returns single test. (2) Regex: 'VDD_.*' matches VDD_CORE, VDD_IO, VDD_LEAKAGE. (3) test_num: 1052 returns test with test number 1052. (4) Range: test_num_start=100, test_num_end=200 returns all tests in that range. (5) Test suite: test_suite_name='Bt5gRxIp2' returns all tests in suite. (6) CSV export: export_csv=true writes results to CSV file and returns minimal response when successful. Use result_limit to control batch size (1-10000).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Absolute path to STDF V4 file",
                            },
                            "test_name": {
                                "type": "string",
                                "description": "Test parameter name (exact match) or regex pattern. Regex examples: 'VDD_.*' (all VDD tests), '.*VOLTAGE.*' (contains VOLTAGE), '^MAIN\\\\..*' (starts with MAIN.), 'TEST_[0-9]+' (numeric suffix). Optional if test_num, range, or test_suite_name provided. Mutually exclusive with test_num, range, and test_suite_name.",
                            },
                            "test_num": {
                                "type": "integer",
                                "description": "Single test number to search (0 to 2^32-1). Use this for direct test ID lookup. Faster than name-based search. Optional if test_name, range, or test_suite_name provided. Mutually exclusive with test_name, range, and test_suite_name.",
                                "minimum": 0,
                                "maximum": 4294967295,
                            },
                            "test_num_start": {
                                "type": "integer",
                                "description": "Range start test number (inclusive). Must be used with test_num_end. Range size limited to 10000. Optional if test_name, test_num, or test_suite_name provided. Mutually exclusive with test_name, test_num, and test_suite_name.",
                                "minimum": 0,
                                "maximum": 4294967295,
                            },
                            "test_num_end": {
                                "type": "integer",
                                "description": "Range end test number (inclusive). Must be used with test_num_start. Range size limited to 10000. Optional if test_name, test_num, or test_suite_name provided. Mutually exclusive with test_name, test_num, and test_suite_name.",
                                "minimum": 0,
                                "maximum": 4294967295,
                            },
                            "test_suite_name": {
                                "type": "string",
                                "description": "Test suite name filter (simple or qualified). Examples: 'Bt5gRxIp2' (simple), 'Main.RxIp2.Bt5gRxIp2' (qualified). Returns summaries for all tests in suite. Optional if test_name, test_num, or range provided. Mutually exclusive with test_name, test_num, and range.",
                            },
                            "is_suite_qualified": {
                                "type": "boolean",
                                "description": "If true, treat test_suite_name as fully qualified path. Default: false",
                                "default": False,
                            },
                            "use_regex": {
                                "type": "boolean",
                                "description": "If true, treat test_name as Python regex pattern for batch extraction. Default: false",
                                "default": False,
                            },
                            "include_derived_metrics": {
                                "type": "boolean",
                                "description": "Calculate derived metrics (pass rate, mean, stddev). Default: true",
                                "default": True,
                            },
                            "result_limit": {
                                "type": "integer",
                                "description": "Maximum number of summaries to return (for regex batch queries, range queries, or test suite queries). Range: 1-10000. Default: 1000. Use lower values for faster performance.",
                                "minimum": 1,
                                "maximum": 10000,
                                "default": 1000,
                            },
                            "export_csv": {
                                "type": "boolean",
                                "description": "Enable CSV file export of test parameter summaries. When true, generates a CSV file in addition to JSON response. Default: false",
                                "default": False,
                            },
                            "output_directory": {
                                "type": "string",
                                "description": "Directory path for CSV output. Can be relative or absolute. Directory will be created if it doesn't exist. Only used when export_csv=true. Default: 'TestCases/Output'",
                                "default": "TestCases/Output",
                            },
                            "csv_aggregation_level": {
                                "type": "string",
                                "description": "CSV aggregation level: 'per_site' (one row per test per site, includes Head_Number and Site_Number columns) or 'overall' (one row per test aggregated across all sites, omits Head/Site columns, 60-70% smaller file size). Only used when export_csv=true. Default: 'per_site' (backward compatible)",
                                "enum": ["per_site", "overall"],
                                "default": "per_site",
                            },
                        },
                        "required": ["file_path"],
                    },
                ),
                # Filtered Data Extraction Tool (Feature 005)
                Tool(
                    name="extract_filtered_data_tool",
                    description="Extract filtered test data from STDF file to column-based Excel file. Supports filtering by test name (regex), test number (single/series/range), test suite name (simple or qualified), and site number. Generates Excel with one row per device and one column per test parameter.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "stdf_file_path": {
                                "type": "string",
                                "description": "Absolute path to STDF-V4 file",
                            },
                            "test_name": {
                                "type": "string",
                                "description": "Test parameter name filter (regex pattern). Examples: '^VDD_CORE$' (exact), 'VDD_.*' (prefix), '.*VOLTAGE.*' (contains). Optional if test_num or test_suite_name provided.",
                            },
                            "test_num": {
                                "type": "array",
                                "items": {
                                    "oneOf": [
                                        {"type": "integer"},
                                        {"type": "string"},
                                    ]
                                },
                                "description": "Test number filter. Supports: single [1052], series [100, 105, 200], range ['100-200'], or mixed [100, '200-250']. Optional if test_name or test_suite_name provided.",
                            },
                            "test_suite_name": {
                                "type": "string",
                                "description": "Test suite name filter (simple or qualified). Examples: 'Bt5gRxIp2' (simple), 'Main.RxIp2.Bt5gRxIp2' (qualified). Optional if test_name or test_num provided. Mutually exclusive with test_name and test_num.",
                            },
                            "is_suite_qualified": {
                                "type": "boolean",
                                "description": "If true, treat test_suite_name as fully qualified path. Default: false",
                                "default": False,
                            },
                            "site_num": {
                                "type": "array",
                                "items": {"type": "integer"},
                                "description": "Site number filter (e.g., [1, 2]). Omit to include all sites.",
                            },
                            "output_directory": {
                                "type": "string",
                                "description": "Absolute path to output directory for Excel file. Defaults to /tmp.",
                                "default": "/tmp",
                            },
                        },
                        "required": ["stdf_file_path"],
                    },
                    outputSchema={
                        "type": "object",
                        "properties": {
                            "excel_file_path": {
                                "type": "string",
                                "description": "Path to generated Excel file",
                            },
                            "total_devices_matched": {
                                "type": "integer",
                                "description": "Number of devices (rows) in Excel file",
                            },
                            "total_test_parameters": {
                                "type": "integer",
                                "description": "Number of test parameters (columns excluding common columns)",
                            },
                            "total_columns": {
                                "type": "integer",
                                "description": "Total columns in Excel (common + test parameters)",
                            },
                            "total_rows": {
                                "type": "integer",
                                "description": "Total rows in Excel file",
                            },
                            "test_parameters": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "test_name": {"type": "string"},
                                        "test_number": {"type": "integer"},
                                        "units": {"type": ["string", "null"]},
                                    },
                                },
                                "description": "List of test parameters included in Excel",
                            },
                            "extraction_time_seconds": {
                                "type": "number",
                                "description": "Time taken to extract and generate Excel",
                            },
                            "test_suite_name": {
                                "type": ["string", "null"],
                                "description": "Test suite name used for filtering (null if not used)",
                            },
                            "test_suite_qualified_path": {
                                "type": ["string", "null"],
                                "description": "Resolved fully qualified suite path (null if not used)",
                            },
                        },
                        "required": [
                            "excel_file_path",
                            "total_devices_matched",
                            "total_test_parameters",
                            "total_columns",
                            "total_rows",
                            "test_parameters",
                            "extraction_time_seconds",
                            "test_suite_name",
                            "test_suite_qualified_path",
                        ],
                    },
                ),
                # Test Time Extraction Tool (Feature 008)
                Tool(
                    name="extract_test_time_tool",
                    description="Extract test execution times from STDF file PRR.TEST_T fields and generate Excel report with statistical analysis. Extracts test time for each device, calculates min/max/mean/standard deviation, and outputs column-based Excel file matching filtered_data format. Supports optional site filtering for multi-site analysis.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "stdf_file_path": {
                                "type": "string",
                                "description": "Absolute path to STDF V4 file containing PRR records with TEST_T field",
                            },
                            "site_num": {
                                "type": "array",
                                "items": {
                                    "type": "integer",
                                    "minimum": 0,
                                    "maximum": 255,
                                },
                                "description": "Optional list of site numbers to filter (e.g., [1, 2]). Omit to include all sites. Valid range: 0-255 per STDF spec.",
                            },
                            "output_directory": {
                                "type": "string",
                                "description": "Absolute path to directory for Excel output. Must exist and be writable. Defaults to '/tmp' if not specified.",
                                "default": "/tmp",
                            },
                        },
                        "required": ["stdf_file_path"],
                    },
                    outputSchema={
                        "type": "object",
                        "properties": {
                            "excel_file_path": {
                                "type": "string",
                                "description": "Absolute path to generated Excel file. Format: <stdf_filename>_TestTime_<YYYYMMDD_HHMMSS>.xlsx",
                            },
                            "total_devices": {
                                "type": "integer",
                                "description": "Total number of devices extracted (includes devices with missing TEST_T)",
                                "minimum": 0,
                            },
                            "valid_devices": {
                                "type": "integer",
                                "description": "Number of devices with valid (non-null) test times used in statistics",
                                "minimum": 0,
                            },
                            "null_devices": {
                                "type": "integer",
                                "description": "Number of devices with missing/null TEST_T values (TEST_T=0)",
                                "minimum": 0,
                            },
                            "min_seconds": {
                                "type": "number",
                                "description": "Minimum test time across all valid devices (seconds)",
                                "minimum": 0,
                            },
                            "max_seconds": {
                                "type": "number",
                                "description": "Maximum test time across all valid devices (seconds)",
                                "minimum": 0,
                            },
                            "mean_seconds": {
                                "type": "number",
                                "description": "Mean (average) test time across all valid devices (seconds)",
                                "minimum": 0,
                            },
                            "std_dev_seconds": {
                                "type": "number",
                                "description": "Population standard deviation of test times (seconds). Formula: σ = sqrt(Σ(xi - μ)² / N)",
                                "minimum": 0,
                            },
                            "extraction_time_seconds": {
                                "type": "number",
                                "description": "Time taken to extract data and generate Excel file (seconds)",
                                "minimum": 0,
                            },
                        },
                        "required": [
                            "excel_file_path",
                            "total_devices",
                            "valid_devices",
                            "null_devices",
                            "min_seconds",
                            "max_seconds",
                            "mean_seconds",
                            "std_dev_seconds",
                            "extraction_time_seconds",
                        ],
                    },
                ),
                # Yield Analysis Tool (Feature 009)
                Tool(
                    name="extract_per_unit_yield_tool",
                    description="Extract per-unit yield data from STDF file and generate CSV report with PART_ID, HW Bin, SW Bin columns. Outputs to TestCases/Output/ directory with timestamped filename. Note: PorF column removed due to unreliable PART_FLG programming by some vendors.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "stdf_file_path": {
                                "type": "string",
                                "description": "Absolute path to STDF V4 file containing PRR records",
                            },
                            "output_directory": {
                                "type": "string",
                                "description": "Directory for CSV output. Defaults to 'TestCases/Output'",
                                "default": "TestCases/Output",
                            },
                        },
                        "required": ["stdf_file_path"],
                    },
                    outputSchema={
                        "type": "object",
                        "properties": {
                            "success": {
                                "type": "boolean",
                                "description": "Whether extraction succeeded",
                            },
                            "csv_file_path": {
                                "type": "string",
                                "description": "Absolute path to generated CSV file (only present if success=true)",
                            },
                            "units_processed": {
                                "type": "integer",
                                "description": "Total number of units extracted from PRR records",
                                "minimum": 0,
                            },
                            "processing_time_ms": {
                                "type": "integer",
                                "description": "Processing time in milliseconds",
                                "minimum": 0,
                            },
                            "error_code": {
                                "type": "string",
                                "description": "Error code (only present if success=false)",
                            },
                            "error_message": {
                                "type": "string",
                                "description": "Error description (only present if success=false)",
                            },
                        },
                        "required": ["success"],
                    },
                ),
            ]

            logger.info(f"📤 JSON RESPONSE: tools/list -> {len(tools)} tools")
            logger.debug(
                f"📤 JSON RESPONSE DETAIL: {[tool.name for tool in tools]}"
            )

            # Flush logs after tool list response
            for handler in logger.handlers:
                if hasattr(handler, "flush"):
                    handler.flush()

            # Populate tools cache for contract testing (Feature 010)
            global _TOOLS_CACHE
            if _TOOLS_CACHE is None:
                _TOOLS_CACHE = tools

            return tools

    def _setup_tools(self) -> None:
        """Setup MCP tools for STDF metadata extraction."""

        # Single handler for ALL tool calls - this is the correct MCP pattern
        @self.server.call_tool()
        async def handle_call_tool(
            name: str, arguments: dict
        ) -> Dict[str, Any]:
            """Handle all tool calls with proper logging.

            Returns the result dictionary directly. The MCP SDK will:
            1. Detect it as structured content (dict)
            2. Validate against outputSchema
            3. Auto-generate both structured and text representations
            4. Return CallToolResult with both content and structuredContent fields
            """
            logger.info(f"📥 JSON REQUEST: tools/call -> tool: {name}")
            logger.debug(
                f"📥 JSON REQUEST DETAIL: arguments: {json.dumps(arguments, indent=2)}"
            )

            # Flush logs immediately for tool calls
            for handler in logger.handlers:
                if hasattr(handler, "flush"):
                    handler.flush()

            try:
                # Get file path - different parameter names for different tools
                file_path = arguments.get("file_path") or arguments.get(
                    "stdf_file_path"
                )
                if not file_path:
                    raise ValueError("file_path or stdf_file_path is required")

                logger.info(f"Processing file: {file_path}")

                # Dispatch to appropriate tool
                if name == "extract_file_overview_tool":
                    result = extract_file_overview(file_path)
                elif name == "extract_test_configuration_tool":
                    result = extract_test_configuration(file_path)
                elif name == "extract_yield_summary_tool":
                    result = extract_yield_summary(file_path)
                elif name == "extract_facility_details_tool":
                    result = extract_facility_details(file_path)
                elif name == "extract_program_metadata_tool":
                    result = extract_program_metadata(file_path)
                elif name == "extract_test_parameters_tool":
                    filter_option = arguments.get(
                        "filter_option", "all_parameters"
                    )
                    result = extract_test_parameters(file_path, filter_option)
                # Record extraction tools
                elif name == "extract_far_record_tool":
                    result = extract_far_record(file_path)
                elif name == "extract_mir_record_tool":
                    result = extract_mir_record(file_path)
                elif name == "extract_hbr_records_tool":
                    result = extract_hbr_records(file_path)
                elif name == "extract_sbr_records_tool":
                    result = extract_sbr_records(file_path)
                elif name == "extract_pcr_records_tool":
                    result = extract_pcr_records(file_path)
                elif name == "extract_sdr_records_tool":
                    result = extract_sdr_records(file_path)
                elif name == "extract_mrr_record_tool":
                    result = extract_mrr_record(file_path)
                # Test parameter summary tool
                elif name == "extract_test_parameter_summary_tool":
                    test_name = arguments.get("test_name")
                    test_num = arguments.get("test_num")
                    test_num_start = arguments.get("test_num_start")
                    test_num_end = arguments.get("test_num_end")
                    test_suite_name = arguments.get("test_suite_name")
                    is_suite_qualified = arguments.get(
                        "is_suite_qualified", False
                    )
                    use_regex = arguments.get("use_regex", False)
                    include_derived_metrics = arguments.get(
                        "include_derived_metrics", True
                    )
                    result_limit = arguments.get("result_limit", 1000)
                    export_csv = arguments.get("export_csv", False)
                    output_directory = arguments.get(
                        "output_directory", "TestCases/Output"
                    )
                    csv_aggregation_level = arguments.get(
                        "csv_aggregation_level", "per_site"
                    )
                    result = extract_test_parameter_summary(
                        file_path,
                        test_name=test_name,
                        use_regex=use_regex,
                        include_derived_metrics=include_derived_metrics,
                        result_limit=result_limit,
                        test_num=test_num,
                        test_num_start=test_num_start,
                        test_num_end=test_num_end,
                        test_suite_name=test_suite_name,
                        is_suite_qualified=is_suite_qualified,
                        export_csv=export_csv,
                        output_directory=output_directory,
                        csv_aggregation_level=csv_aggregation_level,
                    )
                # Filtered data extraction tool
                elif name == "extract_filtered_data_tool":
                    test_name = arguments.get("test_name")
                    test_num = arguments.get("test_num")
                    test_suite_name = arguments.get("test_suite_name")
                    is_suite_qualified = arguments.get(
                        "is_suite_qualified", False
                    )
                    site_num = arguments.get("site_num")
                    output_directory = arguments.get(
                        "output_directory", "/tmp"
                    )
                    result = extract_filtered_data(
                        stdf_file_path=file_path,
                        test_name=test_name,
                        test_num=test_num,
                        test_suite_name=test_suite_name,
                        is_suite_qualified=is_suite_qualified,
                        site_num=site_num,
                        output_directory=output_directory,
                    )
                # Test time extraction tool
                elif name == "extract_test_time_tool":
                    site_num = arguments.get("site_num")
                    output_directory = arguments.get(
                        "output_directory", "/tmp"
                    )
                    result = extract_test_time(
                        stdf_file_path=file_path,
                        site_num=site_num,
                        output_directory=output_directory,
                    )
                # Yield analysis tool
                elif name == "extract_per_unit_yield_tool":
                    output_directory = arguments.get(
                        "output_directory", "TestCases/Output"
                    )
                    result = extract_per_unit_yield(
                        stdf_file_path=file_path,
                        output_directory=output_directory,
                    )
                else:
                    raise ValueError(f"Unknown tool: {name}")

                logger.debug(f"Tool {name} completed successfully")
                logger.debug(
                    f"Result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}"
                )

                # Log successful JSON response (for debugging)
                result_json = json.dumps(result, indent=2, default=str)
                result_size = len(result_json)
                logger.info(
                    f"📤 JSON RESPONSE: tools/call -> SUCCESS ({result_size} chars)"
                )
                logger.debug(
                    f"📤 JSON RESPONSE DETAIL: {result_json[:500]}{'...' if result_size > 500 else ''}"
                )

                # Flush logs after successful tool completion
                for handler in logger.handlers:
                    if hasattr(handler, "flush"):
                        handler.flush()

                # Return dict directly - MCP SDK will handle structured + text content
                return result

            except Exception as e:
                error_msg = f"Error in {name}: {str(e)}"
                # Log error without full stack trace to avoid duplicate logging
                # The MCP SDK will catch and handle the exception
                logger.info(
                    f"📤 JSON RESPONSE: tools/call -> ERROR: {error_msg}"
                )

                # Flush logs after error
                for handler in logger.handlers:
                    if hasattr(handler, "flush"):
                        handler.flush()

                # Re-raise the exception - let MCP SDK handle error response
                # The SDK will catch this and create a proper CallToolResult with isError=True
                raise

    async def run(self) -> None:
        """Run the Simple STDF MCP server."""
        logger.info("Starting Simple STDF-V4 MCP Server with 17 tools...")
        logger.info("Available tools:")
        logger.info("Metadata Tools:")
        logger.info("  1. extract_file_overview_tool")
        logger.info("  2. extract_test_configuration_tool")
        logger.info("  3. extract_yield_summary_tool")
        logger.info("  4. extract_facility_details_tool")
        logger.info("  5. extract_program_metadata_tool")
        logger.info("  6. extract_test_parameters_tool")
        logger.info("Record Extraction Tools:")
        logger.info("  7. extract_far_record_tool")
        logger.info("  8. extract_mir_record_tool")
        logger.info("  9. extract_hbr_records_tool")
        logger.info("  10. extract_sbr_records_tool")
        logger.info("  11. extract_pcr_records_tool")
        logger.info("  12. extract_sdr_records_tool")
        logger.info("  13. extract_mrr_record_tool")
        logger.info("Test Parameter Summary Tools:")
        logger.info(
            "  14. extract_test_parameter_summary_tool (with test suite filtering)"
        )
        logger.info("Filtered Data Extraction Tools:")
        logger.info(
            "  15. extract_filtered_data_tool (with test suite filtering)"
        )
        logger.info("Test Time Extraction Tools:")
        logger.info(
            "  16. extract_test_time_tool (PRR.TEST_T with statistics and site filtering)"
        )
        logger.info("Yield Analysis Tools:")
        logger.info("  17. extract_per_unit_yield_tool (per-unit P/F to CSV)")

        # Explicitly flush all log handlers to ensure logs are written to file immediately
        for handler in logger.handlers:
            if hasattr(handler, "flush"):
                handler.flush()

        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="stdf-v4-analyzer",
                    server_version="1.0.2",
                    capabilities={
                        "tools": {"subscribe": True, "listChanged": True},
                        "resources": {"subscribe": True, "listChanged": True},
                    },
                ),
            )


def main() -> None:
    """Main entry point for Simple STDF MCP server."""
    server = SimpleSTDFMCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
