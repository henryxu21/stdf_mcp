"""
Extract yield summary metadata from STDF-V4 package test files.

This module provides the extract_yield_summary MCP tool that calculates
part count records, retest information, and computed statistics.

Features:
- Intel CPU little-endian constraint enforcement
- Part count records from PCR records
- Retest information from MRR records
- Computed yield statistics and test duration
- Multi-site yield breakdown
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


class YieldSummaryExtractor:
    """Extract yield summary metadata from STDF-V4 package test files."""

    def __init__(self, config: Optional[ParserConfig] = None):
        """
        Initialize yield summary extractor.

        Args:
            config: Parser configuration (defaults to package test only)
        """
        self.config = config or ParserConfig(
            max_file_size_mb=2048,
            enable_integrity_validation=True,
            package_test_only=True,  # Intel CPU constraint
            max_memory_usage_mb=512
        )

    def extract_yield_summary(self, file_path: str) -> Dict[str, Any]:
        """
        Extract yield summary including part counts, retest info, and computed statistics.

        Args:
            file_path: Absolute path to STDF-V4 package test file

        Returns:
            Dict containing part_count_records, retest_information, and computed_statistics

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
        part_count_records = []
        retest_information = {}
        computed_statistics = {
            "overall_yield": 0.0,
            "total_parts_tested": 0,
            "total_good_parts": 0,
            "total_retests": 0,
            "total_aborts": 0,
            "test_duration": 0.0
        }

        # Track data for computations
        pcr_records_found = 0
        mrr_records_found = 0
        total_parts = 0
        total_good = 0
        total_retests = 0
        total_aborts = 0
        test_start_time = None
        test_end_time = None

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

            # Parse records for yield summary
            for record in parser.parse_records(file_path_obj):
                record_name = getattr(record, 'RECORD_NAME', 'Unknown')

                # Get test timing from MIR record
                if record_name == 'MIR':
                    if hasattr(record, 'start_t') and record.start_t:
                        test_start_time = record.start_t

                # Extract part count records from PCR records
                elif record_name == 'PCR':
                    pcr_records_found += 1

                    pcr_data = {
                        "head_num": getattr(record, 'head_num', None),
                        "site_num": getattr(record, 'site_num', None),
                        "part_cnt": getattr(record, 'part_cnt', 0),
                        "rtst_cnt": getattr(record, 'rtst_cnt', 0),
                        "abrt_cnt": getattr(record, 'abrt_cnt', 0),
                        "good_cnt": getattr(record, 'good_cnt', 0),
                        "func_cnt": getattr(record, 'func_cnt', 0)
                    }

                    # Calculate yield percentage for this site
                    if pcr_data["part_cnt"] > 0:
                        pcr_data["yield_percentage"] = (pcr_data["good_cnt"] / pcr_data["part_cnt"]) * 100.0
                    else:
                        pcr_data["yield_percentage"] = 0.0

                    part_count_records.append(pcr_data)

                    # Accumulate totals
                    total_parts += pcr_data["part_cnt"]
                    total_good += pcr_data["good_cnt"]
                    total_retests += pcr_data["rtst_cnt"]
                    total_aborts += pcr_data["abrt_cnt"]

                # Extract retest information from MRR record
                elif record_name == 'MRR':
                    mrr_records_found += 1

                    retest_information = {
                        "rtst_cod": getattr(record, 'disp_cod', None),  # Use disposition code
                        "finish_time": getattr(record, 'finish_t', None),
                        "usr_desc": getattr(record, 'usr_desc', None),
                        "exc_desc": getattr(record, 'exc_desc', None)
                    }

                    if hasattr(record, 'finish_t') and record.finish_t:
                        test_end_time = record.finish_t

            # Calculate computed statistics
            computed_statistics["total_parts_tested"] = total_parts
            computed_statistics["total_good_parts"] = total_good
            computed_statistics["total_retests"] = total_retests
            computed_statistics["total_aborts"] = total_aborts

            if total_parts > 0:
                computed_statistics["overall_yield"] = (total_good / total_parts) * 100.0

            if test_start_time and test_end_time:
                computed_statistics["test_duration"] = max(0, test_end_time - test_start_time)

            # Add site-level statistics
            site_count = len(part_count_records)
            if site_count > 0:
                computed_statistics["site_count"] = site_count
                computed_statistics["average_yield_per_site"] = sum(pcr["yield_percentage"] for pcr in part_count_records) / site_count
                computed_statistics["best_site_yield"] = max(pcr["yield_percentage"] for pcr in part_count_records)
                computed_statistics["worst_site_yield"] = min(pcr["yield_percentage"] for pcr in part_count_records)

            execution_time = time.time() - start_time

            return {
                "part_count_records": part_count_records,
                "retest_information": retest_information,
                "computed_statistics": computed_statistics,
                "_metadata": {
                    "extraction_time": execution_time,
                    "pcr_records_found": pcr_records_found,
                    "mrr_records_found": mrr_records_found,
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
                raise InvalidSTDFFormatError(f"Error extracting yield summary: {str(e)}", file_path)


def extract_yield_summary(file_path: str) -> Dict[str, Any]:
    """
    MCP tool: Extract yield summary including part counts, retest info, and computed statistics.

    This tool calculates comprehensive yield statistics from STDF-V4 package test files
    with Intel CPU little-endian constraint enforcement.

    Args:
        file_path: Absolute path to STDF-V4 package test file

    Returns:
        Dict containing:
        - part_count_records: Per-site part count and yield data
        - retest_information: Retest codes and disposition information
        - computed_statistics: Overall yield metrics and test duration

    Raises:
        UnsupportedCPUArchitectureError: If file is not Intel CPU little-endian
        UnsupportedSTDFVersionError: If file is not STDF-V4
        UnsupportedTestScopeError: If file contains wafer test data
        InvalidSTDFFormatError: If file format is invalid
    """
    extractor = YieldSummaryExtractor()
    return extractor.extract_yield_summary(file_path)


# For testing and debugging
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract STDF yield summary")
    parser.add_argument("file_path", help="Path to STDF file")
    args = parser.parse_args()

    try:
        result = extract_yield_summary(args.file_path)
        import json
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)