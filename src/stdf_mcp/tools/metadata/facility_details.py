"""
Extract facility details metadata from STDF-V4 package test files.

This module provides the extract_facility_details MCP tool that extracts
location information, process information, engineering context, and timing information.

Features:
- Intel CPU little-endian constraint enforcement
- Location information extraction from MIR records
- Process and engineering context details
- Timing information with proper timestamp conversion
- Manufacturing traceability data
"""

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

# Add src to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from stdf_mcp.stdf.parser import STDFV4Parser, ParserConfig
from stdf_mcp.stdf.exceptions import *
from stdf_mcp.stdf.types import format_stdf_timestamp


class FacilityDetailsExtractor:
    """Extract facility details metadata from STDF-V4 package test files."""

    def __init__(self, config: Optional[ParserConfig] = None):
        """
        Initialize facility details extractor.

        Args:
            config: Parser configuration (defaults to package test only)
        """
        self.config = config or ParserConfig(
            max_file_size_mb=2048,
            enable_integrity_validation=True,
            package_test_only=True,  # Intel CPU constraint
            max_memory_usage_mb=512
        )

    def extract_facility_details(self, file_path: str) -> Dict[str, Any]:
        """
        Extract facility details including location, process, engineering, and timing information.

        Args:
            file_path: Absolute path to STDF-V4 package test file

        Returns:
            Dict containing location_information, process_information, engineering_context, timing_information

        Raises:
            UnsupportedCPUArchitectureError: If file is not Intel CPU little-endian
            UnsupportedSTDFVersionError: If file is not STDF-V4
            InvalidSTDFFormatError: If file format is invalid
        """
        start_time = time.time()

        # Validate file path
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise InvalidSTDFFormatError(f"File does not exist: {file_path}", file_path)

        # Initialize parser
        parser = STDFV4Parser(self.config)

        # Initialize result containers
        location_information = {}
        process_information = {}
        engineering_context = {}
        timing_information = {}

        # Track what we find
        mir_records_found = 0

        try:
            # Validate file format first (enforces Intel CPU constraint)
            is_valid, stdf_version = parser.validate_stdf_format(file_path_obj)
            endianness = parser.detect_endianness(file_path_obj)
            parser.validate_package_test_scope(file_path_obj)

            # Verify Intel CPU constraint
            if endianness != "little":
                raise UnsupportedCPUArchitectureError(
                    f"Non-Intel CPU architecture detected: {endianness}. "
                    f"Only Intel CPU little-endian files are supported.",
                    endianness
                )

            # Parse records for facility details
            for record in parser.parse_records(file_path_obj):
                record_name = getattr(record, 'RECORD_NAME', 'Unknown')

                # Extract facility details from MIR record
                if record_name == 'MIR':
                    mir_records_found += 1

                    # Location information
                    location_information = {
                        "facil_id": getattr(record, 'facil_id', None),
                        "floor_id": getattr(record, 'floor_id', None),
                        "stat_num": getattr(record, 'stat_num', None),
                        "node_nam": getattr(record, 'node_nam', None)
                    }

                    # Process information
                    process_information = {
                        "proc_id": getattr(record, 'proc_id', None),
                        "famly_id": getattr(record, 'famly_id', None),
                        "pkg_typ": getattr(record, 'pkg_typ', None),
                        "dsgn_rev": getattr(record, 'dsgn_rev', None),
                        "part_typ": getattr(record, 'part_typ', None),
                        "date_cod": getattr(record, 'date_cod', None),
                        "oper_frq": getattr(record, 'oper_frq', None)
                    }

                    # Engineering context
                    engineering_context = {
                        "eng_id": getattr(record, 'eng_id', None),
                        "rom_cod": getattr(record, 'rom_cod', None),
                        "sblot_id": getattr(record, 'sblot_id', None),
                        "oper_nam": getattr(record, 'oper_nam', None),
                        "supr_nam": getattr(record, 'supr_nam', None),
                        "lot_id": getattr(record, 'lot_id', None)
                    }

                    # Timing information (convert STDF timestamps to Unix epoch)
                    timing_information = {
                        "setup_t": getattr(record, 'setup_t', None),
                        "start_t": getattr(record, 'start_t', None)
                    }

                    # Convert timestamps to ISO format for better readability
                    if timing_information["setup_t"]:
                        try:
                            setup_dt = format_stdf_timestamp(timing_information["setup_t"])
                            timing_information["setup_time_iso"] = setup_dt.isoformat() if setup_dt else None
                        except:
                            timing_information["setup_time_iso"] = None

                    if timing_information["start_t"]:
                        try:
                            start_dt = format_stdf_timestamp(timing_information["start_t"])
                            timing_information["start_time_iso"] = start_dt.isoformat() if start_dt else None
                        except:
                            timing_information["start_time_iso"] = None

                    # Only need the first MIR record for facility details
                    break

            execution_time = time.time() - start_time

            return {
                "location_information": location_information,
                "process_information": process_information,
                "engineering_context": engineering_context,
                "timing_information": timing_information,
                "_metadata": {
                    "extraction_time": execution_time,
                    "mir_records_found": mir_records_found,
                    "tool_version": "1.0.0"
                }
            }

        except Exception as e:
            execution_time = time.time() - start_time
            # Re-raise with additional context
            if isinstance(e, (UnsupportedCPUArchitectureError, UnsupportedSTDFVersionError,
                            UnsupportedTestScopeError, InvalidSTDFFormatError)):
                raise
            else:
                raise InvalidSTDFFormatError(f"Error extracting facility details: {str(e)}", file_path)


def extract_facility_details(file_path: str) -> Dict[str, Any]:
    """
    MCP tool: Extract facility details including location, process, engineering, and timing information.

    This tool extracts manufacturing and facility context from STDF-V4 package test files
    with Intel CPU little-endian constraint enforcement.

    Args:
        file_path: Absolute path to STDF-V4 package test file

    Returns:
        Dict containing:
        - location_information: Test facility and station details
        - process_information: Manufacturing process and device details
        - engineering_context: Engineering IDs and traceability
        - timing_information: Test setup and execution timestamps

    Raises:
        UnsupportedCPUArchitectureError: If file is not Intel CPU little-endian
        UnsupportedSTDFVersionError: If file is not STDF-V4
        UnsupportedTestScopeError: If file contains wafer test data
        InvalidSTDFFormatError: If file format is invalid
    """
    extractor = FacilityDetailsExtractor()
    return extractor.extract_facility_details(file_path)


# For testing and debugging
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract STDF facility details")
    parser.add_argument("file_path", help="Path to STDF file")
    args = parser.parse_args()

    try:
        result = extract_facility_details(args.file_path)
        import json
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)