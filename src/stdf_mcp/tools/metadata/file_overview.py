"""
Extract file overview metadata from STDF-V4 package test files.

This module provides the extract_file_overview MCP tool that generates
quick file assessment with key identifiers and summary statistics.

Features:
- Intel CPU little-endian constraint enforcement
- File format validation (STDF-V4 only)
- Package test scope validation (no wafer test data)
- Automatic integrity validation
- Performance optimized for <5s response time
"""

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

# Add src to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from stdf_mcp.stdf.parser import STDFV4Parser, ParserConfig
from stdf_mcp.stdf.exceptions import *
from stdf_mcp.stdf.types import format_stdf_timestamp


class FileOverviewExtractor:
    """Extract file overview metadata from STDF-V4 package test files."""

    def __init__(self, config: Optional[ParserConfig] = None):
        """
        Initialize file overview extractor.

        Args:
            config: Parser configuration (defaults to package test only)
        """
        self.config = config or ParserConfig(
            max_file_size_mb=2048,
            enable_integrity_validation=True,
            package_test_only=True,  # Intel CPU constraint
            max_memory_usage_mb=512
        )

    def extract_file_overview(self, file_path: str) -> Dict[str, Any]:
        """
        Extract file overview with key identifiers and summary statistics.

        Args:
            file_path: Absolute path to STDF-V4 package test file

        Returns:
            Dict containing file_info, key_identifiers, and summary_statistics

        Raises:
            UnsupportedCPUArchitectureError: If file is not Intel CPU little-endian
            UnsupportedSTDFVersionError: If file is not STDF-V4
            UnsupportedTestScopeError: If file contains wafer test data
            InvalidSTDFFormatError: If file format is invalid
            FileSizeExceededError: If file exceeds size limits
        """
        start_time = time.time()

        # Validate file path
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise InvalidSTDFFormatError(f"File does not exist: {file_path}", file_path)

        # Initialize parser
        parser = STDFV4Parser(self.config)

        # Initialize result containers
        file_info = {}
        key_identifiers = {}
        summary_statistics = {
            "total_records": 0,
            "total_test_time": 0.0,
            "parts_tested": 0,
            "total_test_sites": 0,
            "overall_yield": 0.0
        }

        # Track record counts and identifiers
        record_counts = {}
        test_sites = set()
        parts_tested_count = 0
        total_good_parts = 0
        test_start_time = None
        test_end_time = None

        try:
            # Validate file format first (enforces Intel CPU constraint)
            is_valid, stdf_version = parser.validate_stdf_format(file_path_obj)
            endianness = parser.detect_endianness(file_path_obj)
            parser.validate_package_test_scope(file_path_obj)

            # Get file info
            file_stat = file_path_obj.stat()
            file_info = {
                "file_path": str(file_path_obj.absolute()),
                "file_size": file_stat.st_size,
                "stdf_version": stdf_version,
                "cpu_type": endianness,  # Will be "little" for Intel CPU
                "creation_time": datetime.fromtimestamp(file_stat.st_ctime, tz=timezone.utc).isoformat(),
                "modification_time": datetime.fromtimestamp(file_stat.st_mtime, tz=timezone.utc).isoformat()
            }

            # Parse records for summary statistics and key identifiers
            for record in parser.parse_records(file_path_obj):
                record_name = getattr(record, 'RECORD_NAME', 'Unknown')
                summary_statistics["total_records"] += 1

                # Count record types
                record_counts[record_name] = record_counts.get(record_name, 0) + 1

                # Extract key identifiers from MIR record
                if record_name == 'MIR':
                    key_identifiers.update({
                        "lot_id": getattr(record, 'lot_id', None),
                        "part_typ": getattr(record, 'part_typ', None),
                        "wafer_id": getattr(record, 'sblot_id', None),  # Use sublot as wafer equivalent
                        "device_type": getattr(record, 'famly_id', None),
                        "test_program": getattr(record, 'job_nam', None),
                        "facility_id": getattr(record, 'facil_id', None)
                    })

                    # Get test timing
                    if hasattr(record, 'start_t') and record.start_t:
                        test_start_time = record.start_t

                # Track sites from PIR records
                elif record_name == 'PIR':
                    if hasattr(record, 'site_num'):
                        test_sites.add(record.site_num)

                # Track part counts and yield from PRR records
                elif record_name == 'PRR':
                    parts_tested_count += 1
                    if hasattr(record, 'part_flg'):
                        # Check if part passed (part_flg bit 4-7 = 0 means pass)
                        if (record.part_flg & 0xF0) == 0:
                            total_good_parts += 1

                # Get test end time from MRR record
                elif record_name == 'MRR':
                    if hasattr(record, 'finish_t') and record.finish_t:
                        test_end_time = record.finish_t

                # Limit parsing for performance (break if we have enough data)
                if summary_statistics["total_records"] > 100000:
                    break

            # Calculate derived statistics
            summary_statistics["total_test_sites"] = len(test_sites)
            summary_statistics["parts_tested"] = parts_tested_count

            if parts_tested_count > 0:
                summary_statistics["overall_yield"] = (total_good_parts / parts_tested_count) * 100.0

            if test_start_time and test_end_time:
                summary_statistics["total_test_time"] = max(0, test_end_time - test_start_time)

            # Verify Intel CPU constraint was enforced
            if file_info["cpu_type"] != "little":
                raise UnsupportedCPUArchitectureError(
                    f"Non-Intel CPU architecture detected: {file_info['cpu_type']}. "
                    f"Only Intel CPU little-endian files are supported.",
                    file_info["cpu_type"]
                )

            execution_time = time.time() - start_time

            return {
                "file_info": file_info,
                "key_identifiers": key_identifiers,
                "summary_statistics": summary_statistics,
                "_metadata": {
                    "extraction_time": execution_time,
                    "record_counts": record_counts,
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
                raise InvalidSTDFFormatError(f"Error extracting file overview: {str(e)}", file_path)


def extract_file_overview(file_path: str) -> Dict[str, Any]:
    """
    MCP tool: Extract file overview with key identifiers and summary statistics.

    This tool provides immediate file assessment for STDF-V4 package test files
    with Intel CPU little-endian constraint enforcement.

    Args:
        file_path: Absolute path to STDF-V4 package test file

    Returns:
        Dict containing:
        - file_info: File metadata and format information
        - key_identifiers: Essential test lot identifiers
        - summary_statistics: High-level test execution metrics

    Raises:
        UnsupportedCPUArchitectureError: If file is not Intel CPU little-endian
        UnsupportedSTDFVersionError: If file is not STDF-V4
        UnsupportedTestScopeError: If file contains wafer test data
        InvalidSTDFFormatError: If file format is invalid
        FileSizeExceededError: If file exceeds 2GB limit
    """
    extractor = FileOverviewExtractor()
    return extractor.extract_file_overview(file_path)


# For testing and debugging
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract STDF file overview")
    parser.add_argument("file_path", help="Path to STDF file")
    args = parser.parse_args()

    try:
        result = extract_file_overview(args.file_path)
        import json
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)