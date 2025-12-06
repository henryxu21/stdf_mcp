"""
Extract test parameters metadata from STDF-V4 package test files.

This module provides the extract_test_parameters MCP tool that extracts
parameters with limits, parameters without limits, and provides filtering options.

Features:
- Intel CPU little-endian constraint enforcement
- Parameters with limits from PTR records
- Parameters without limits from FTR records
- Filter options: with_limits_only, without_limits_only, all_parameters
- Parametric vs functional test categorization
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


class TestParametersExtractor:
    """Extract test parameters metadata from STDF-V4 package test files."""

    def __init__(self, config: Optional[ParserConfig] = None):
        """
        Initialize test parameters extractor.

        Args:
            config: Parser configuration (defaults to package test only)
        """
        self.config = config or ParserConfig(
            max_file_size_mb=2048,
            enable_integrity_validation=True,
            package_test_only=True,  # Intel CPU constraint
            max_memory_usage_mb=512
        )

    def extract_test_parameters(self, file_path: str, filter_option: str = "all_parameters") -> Dict[str, Any]:
        """
        Extract test parameters with optional filtering.

        Args:
            file_path: Absolute path to STDF-V4 package test file
            filter_option: "all_parameters", "with_limits_only", or "without_limits_only"

        Returns:
            Dict containing parameters_with_limits, parameters_without_limits, and counts

        Raises:
            UnsupportedCPUArchitectureError: If file is not Intel CPU little-endian
            UnsupportedSTDFVersionError: If file is not STDF-V4
            InvalidSTDFFormatError: If file format is invalid
            ValueError: If filter_option is invalid
        """
        start_time = time.time()

        # Validate filter option
        valid_filters = ["all_parameters", "with_limits_only", "without_limits_only"]
        if filter_option not in valid_filters:
            raise ValueError(f"Invalid filter_option: {filter_option}. Must be one of {valid_filters}")

        # Validate file path
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise InvalidSTDFFormatError(f"File does not exist: {file_path}", file_path)

        # Initialize parser
        parser = STDFV4Parser(self.config)

        # Initialize result containers
        parameters_with_limits = []
        parameters_without_limits = []

        # Track record counts
        ptr_records_found = 0
        ftr_records_found = 0
        unique_tests = set()

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

            # Parse records for test parameters
            for record in parser.parse_records(file_path_obj):
                record_name = getattr(record, 'RECORD_NAME', 'Unknown')

                # Extract parameters with limits from PTR records
                if record_name == 'PTR':
                    ptr_records_found += 1

                    test_number = getattr(record, 'test_num', None)
                    if test_number is not None:
                        unique_tests.add(test_number)

                    # Only collect PTR data if filter allows it
                    if filter_option in ["all_parameters", "with_limits_only"]:
                        ptr_data = {
                            "test_number": test_number,
                            "test_name": getattr(record, 'test_txt', None),
                            "units": getattr(record, 'units', None),
                            "low_limit": getattr(record, 'lo_limit', None),
                            "high_limit": getattr(record, 'hi_limit', None),
                            "low_spec": getattr(record, 'lo_spec', None),
                            "high_spec": getattr(record, 'hi_spec', None),
                            "test_flag": self._interpret_test_flag(getattr(record, 'test_flg', 0)),
                            "test_type": "parametric",
                            "result": getattr(record, 'result', None),
                            "alarm_id": getattr(record, 'alarm_id', None),
                            "opt_flag": getattr(record, 'opt_flag', None)
                        }

                        parameters_with_limits.append(ptr_data)

                # Extract parameters without limits from FTR records
                elif record_name == 'FTR':
                    ftr_records_found += 1

                    test_number = getattr(record, 'test_num', None)
                    if test_number is not None:
                        unique_tests.add(test_number)

                    # Only collect FTR data if filter allows it
                    if filter_option in ["all_parameters", "without_limits_only"]:
                        ftr_data = {
                            "test_number": test_number,
                            "test_name": getattr(record, 'test_txt', None),
                            "units": None,  # FTR typically doesn't have units
                            "test_flag": self._interpret_test_flag(getattr(record, 'test_flg', 0)),
                            "test_type": "functional",
                            "vect_nam": getattr(record, 'vect_nam', None),
                            "time_set": getattr(record, 'time_set', None),
                            "op_code": getattr(record, 'op_code', None),
                            "test_tim": getattr(record, 'test_tim', None),
                            "loop_cnt": getattr(record, 'loop_cnt', None),
                            "prog_cnt": getattr(record, 'prog_cnt', None),
                            "fail_cnt": getattr(record, 'fail_cnt', None),
                            "alarm_id": getattr(record, 'alarm_id', None),
                            "opt_flag": getattr(record, 'opt_flag', None)
                        }

                        parameters_without_limits.append(ftr_data)

                # Performance optimization - limit record processing
                if ptr_records_found + ftr_records_found > 50000:
                    break

            # Calculate counts based on filter
            total_parameter_count = 0
            parametric_test_count = 0
            functional_test_count = 0

            if filter_option == "all_parameters":
                total_parameter_count = len(parameters_with_limits) + len(parameters_without_limits)
                parametric_test_count = len(parameters_with_limits)
                functional_test_count = len(parameters_without_limits)
            elif filter_option == "with_limits_only":
                total_parameter_count = len(parameters_with_limits)
                parametric_test_count = len(parameters_with_limits)
                functional_test_count = 0
                parameters_without_limits = []  # Clear for consistency
            elif filter_option == "without_limits_only":
                total_parameter_count = len(parameters_without_limits)
                parametric_test_count = 0
                functional_test_count = len(parameters_without_limits)
                parameters_with_limits = []  # Clear for consistency

            execution_time = time.time() - start_time

            return {
                "parameters_with_limits": parameters_with_limits,
                "parameters_without_limits": parameters_without_limits,
                "total_parameter_count": total_parameter_count,
                "parametric_test_count": parametric_test_count,
                "functional_test_count": functional_test_count,
                "filter_option": filter_option,
                "_metadata": {
                    "extraction_time": execution_time,
                    "ptr_records_found": ptr_records_found,
                    "ftr_records_found": ftr_records_found,
                    "unique_test_numbers": len(unique_tests),
                    "tool_version": "1.0.0"
                }
            }

        except Exception as e:
            execution_time = time.time() - start_time
            # Re-raise with additional context
            if isinstance(e, (UnsupportedCPUArchitectureError, UnsupportedSTDFVersionError,
                            UnsupportedTestScopeError, InvalidSTDFFormatError, ValueError)):
                raise
            else:
                raise InvalidSTDFFormatError(f"Error extracting test parameters: {str(e)}", file_path)

    def _interpret_test_flag(self, test_flag: int) -> str:
        """
        Interpret test flag value into human-readable string.

        Args:
            test_flag: Integer test flag value

        Returns:
            String interpretation of test flag
        """
        if test_flag == 0:
            return "PASS"
        elif test_flag & 0x01:
            return "FAIL"
        elif test_flag & 0x02:
            return "ALARM"
        elif test_flag & 0x04:
            return "INVALID"
        elif test_flag & 0x08:
            return "UNRELIABLE"
        elif test_flag & 0x10:
            return "TIMEOUT"
        elif test_flag & 0x20:
            return "NOT_TESTED"
        else:
            return f"FLAG_{test_flag:02X}"


def extract_test_parameters(file_path: str, filter_option: str = "all_parameters") -> Dict[str, Any]:
    """
    MCP tool: Extract test parameters with optional filtering.

    This tool extracts test parameter information from STDF-V4 package test files
    with Intel CPU little-endian constraint enforcement.

    Args:
        file_path: Absolute path to STDF-V4 package test file
        filter_option: "all_parameters", "with_limits_only", or "without_limits_only"

    Returns:
        Dict containing:
        - parameters_with_limits: Parametric test data with limit specifications
        - parameters_without_limits: Functional test data without limits
        - total_parameter_count: Total count based on filter
        - parametric_test_count: Count of parametric tests
        - functional_test_count: Count of functional tests
        - filter_option: Applied filter option

    Raises:
        UnsupportedCPUArchitectureError: If file is not Intel CPU little-endian
        UnsupportedSTDFVersionError: If file is not STDF-V4
        UnsupportedTestScopeError: If file contains wafer test data
        InvalidSTDFFormatError: If file format is invalid
        ValueError: If filter_option is invalid
    """
    extractor = TestParametersExtractor()
    return extractor.extract_test_parameters(file_path, filter_option)


# For testing and debugging
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract STDF test parameters")
    parser.add_argument("file_path", help="Path to STDF file")
    parser.add_argument("--filter", default="all_parameters",
                       choices=["all_parameters", "with_limits_only", "without_limits_only"],
                       help="Filter option for parameters")
    args = parser.parse_args()

    try:
        result = extract_test_parameters(args.file_path, args.filter)
        import json
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)