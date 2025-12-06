"""
Extract test configuration metadata from STDF-V4 package test files.

This module provides the extract_test_configuration MCP tool that extracts
test conditions, hardware configuration, and site descriptions.

Features:
- Intel CPU little-endian constraint enforcement
- Test conditions extraction from MIR records
- Hardware configuration details
- Site descriptions from SDR records
- Multi-site configuration support
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


class TestConfigurationExtractor:
    """Extract test configuration metadata from STDF-V4 package test files."""

    def __init__(self, config: Optional[ParserConfig] = None):
        """
        Initialize test configuration extractor.

        Args:
            config: Parser configuration (defaults to package test only)
        """
        self.config = config or ParserConfig(
            max_file_size_mb=2048,
            enable_integrity_validation=True,
            package_test_only=True,  # Intel CPU constraint
            max_memory_usage_mb=512
        )

    def extract_test_configuration(self, file_path: str) -> Dict[str, Any]:
        """
        Extract test configuration including conditions, hardware, and site descriptions.

        Args:
            file_path: Absolute path to STDF-V4 package test file

        Returns:
            Dict containing test_conditions, hardware_configuration, and site_descriptions

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
        test_conditions = {}
        hardware_configuration = {}
        site_descriptions = []

        # Track what we find
        mir_records_found = 0
        sdr_records_found = 0

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

            # Parse records for test configuration
            for record in parser.parse_records(file_path_obj):
                record_name = getattr(record, 'RECORD_NAME', 'Unknown')

                # Extract test conditions and hardware configuration from MIR record
                if record_name == 'MIR':
                    mir_records_found += 1

                    # Test conditions from MIR
                    test_conditions = {
                        "tst_temp": getattr(record, 'tst_temp', None),
                        "mode_cod": getattr(record, 'mode_cod', None),
                        "setup_id": getattr(record, 'setup_id', None),
                        "flow_id": getattr(record, 'flow_id', None),
                        "exec_typ": getattr(record, 'exec_typ', None),
                        "exec_ver": getattr(record, 'exec_ver', None),
                        "test_cod": getattr(record, 'test_cod', None)
                    }

                    # Hardware configuration from MIR
                    hardware_configuration = {
                        "serl_num": getattr(record, 'serl_num', None),
                        "tstr_typ": getattr(record, 'tstr_typ', None),
                        "node_nam": getattr(record, 'node_nam', None),
                        "stat_num": getattr(record, 'stat_num', None)
                    }

                # Extract site descriptions from SDR records
                elif record_name == 'SDR':
                    sdr_records_found += 1

                    site_description = {
                        "site_cnt": getattr(record, 'site_cnt', None),
                        "site_num": getattr(record, 'site_num', None),
                        "hand_id": getattr(record, 'hand_id', None),
                        "load_id": getattr(record, 'load_id', None),
                        "dib_id": getattr(record, 'dib_id', None),
                        "card_id": getattr(record, 'card_id', None),
                        "load_nam": getattr(record, 'load_nam', None),
                        "dib_nam": getattr(record, 'dib_nam', None),
                        "cabl_id": getattr(record, 'cabl_id', None),
                        "cont_id": getattr(record, 'cont_id', None),
                        "lasr_id": getattr(record, 'lasr_id', None),
                        "extr_id": getattr(record, 'extr_id', None)
                    }

                    site_descriptions.append(site_description)

                # Stop processing if we have all MIR/SDR records (performance optimization)
                if mir_records_found >= 1 and sdr_records_found > 0:
                    # Continue a bit more to collect additional SDR records if present
                    pass

            execution_time = time.time() - start_time

            return {
                "test_conditions": test_conditions,
                "hardware_configuration": hardware_configuration,
                "site_descriptions": site_descriptions,
                "_metadata": {
                    "extraction_time": execution_time,
                    "mir_records_found": mir_records_found,
                    "sdr_records_found": sdr_records_found,
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
                raise InvalidSTDFFormatError(f"Error extracting test configuration: {str(e)}", file_path)


def extract_test_configuration(file_path: str) -> Dict[str, Any]:
    """
    MCP tool: Extract test configuration including conditions, hardware, and site descriptions.

    This tool extracts test setup information from STDF-V4 package test files
    with Intel CPU little-endian constraint enforcement.

    Args:
        file_path: Absolute path to STDF-V4 package test file

    Returns:
        Dict containing:
        - test_conditions: Test environment and execution parameters
        - hardware_configuration: Tester hardware identification
        - site_descriptions: Multi-site configuration details

    Raises:
        UnsupportedCPUArchitectureError: If file is not Intel CPU little-endian
        UnsupportedSTDFVersionError: If file is not STDF-V4
        UnsupportedTestScopeError: If file contains wafer test data
        InvalidSTDFFormatError: If file format is invalid
    """
    extractor = TestConfigurationExtractor()
    return extractor.extract_test_configuration(file_path)


# For testing and debugging
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract STDF test configuration")
    parser.add_argument("file_path", help="Path to STDF file")
    args = parser.parse_args()

    try:
        result = extract_test_configuration(args.file_path)
        import json
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)