"""
Extract program metadata from STDF-V4 package test files.

This module provides the extract_program_metadata MCP tool that extracts
program identification, specifications, tester software, and user context.

Features:
- Intel CPU little-endian constraint enforcement
- Program identification from MIR records
- Test specifications and version information
- Tester software details
- User context and program execution information
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


class ProgramMetadataExtractor:
    """Extract program metadata from STDF-V4 package test files."""

    def __init__(self, config: Optional[ParserConfig] = None):
        """
        Initialize program metadata extractor.

        Args:
            config: Parser configuration (defaults to package test only)
        """
        self.config = config or ParserConfig(
            max_file_size_mb=2048,
            enable_integrity_validation=True,
            package_test_only=True,  # Intel CPU constraint
            max_memory_usage_mb=512
        )

    def extract_program_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Extract program metadata including identification, specifications, software, and user context.

        Args:
            file_path: Absolute path to STDF-V4 package test file

        Returns:
            Dict containing program_identification, specifications, tester_software, user_context

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
        program_identification = {}
        specifications = {}
        tester_software = {}
        user_context = {}

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

            # Parse records for program metadata
            for record in parser.parse_records(file_path_obj):
                record_name = getattr(record, 'RECORD_NAME', 'Unknown')

                # Extract program metadata from MIR record
                if record_name == 'MIR':
                    mir_records_found += 1

                    # Program identification
                    program_identification = {
                        "job_nam": getattr(record, 'job_nam', None),
                        "job_rev": getattr(record, 'job_rev', None),
                        "aux_file": getattr(record, 'aux_file', None),
                        "lot_id": getattr(record, 'lot_id', None),
                        "part_typ": getattr(record, 'part_typ', None)
                    }

                    # Specifications
                    specifications = {
                        "spec_nam": getattr(record, 'spec_nam', None),
                        "spec_ver": getattr(record, 'spec_ver', None),
                        "flow_id": getattr(record, 'flow_id', None),
                        "setup_id": getattr(record, 'setup_id', None),
                        "dsgn_rev": getattr(record, 'dsgn_rev', None),
                        "date_cod": getattr(record, 'date_cod', None)
                    }

                    # Tester software
                    tester_software = {
                        "exec_typ": getattr(record, 'exec_typ', None),
                        "exec_ver": getattr(record, 'exec_ver', None),
                        "tstr_typ": getattr(record, 'tstr_typ', None),
                        "serl_num": getattr(record, 'serl_num', None),
                        "mode_cod": getattr(record, 'mode_cod', None),
                        "cmod_cod": getattr(record, 'cmod_cod', None)
                    }

                    # User context
                    user_context = {
                        "user_txt": getattr(record, 'user_txt', None),
                        "test_cod": getattr(record, 'test_cod', None),
                        "oper_nam": getattr(record, 'oper_nam', None),
                        "supr_nam": getattr(record, 'supr_nam', None),
                        "eng_id": getattr(record, 'eng_id', None),
                        "rtst_cod": getattr(record, 'rtst_cod', None),
                        "prot_cod": getattr(record, 'prot_cod', None)
                    }

                    # Only need the first MIR record for program metadata
                    break

            # Add derived information
            if program_identification.get("job_nam") and program_identification.get("job_rev"):
                program_identification["full_program_name"] = f"{program_identification['job_nam']} v{program_identification['job_rev']}"

            if specifications.get("spec_nam") and specifications.get("spec_ver"):
                specifications["full_specification"] = f"{specifications['spec_nam']} {specifications['spec_ver']}"

            execution_time = time.time() - start_time

            return {
                "program_identification": program_identification,
                "specifications": specifications,
                "tester_software": tester_software,
                "user_context": user_context,
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
                raise InvalidSTDFFormatError(f"Error extracting program metadata: {str(e)}", file_path)


def extract_program_metadata(file_path: str) -> Dict[str, Any]:
    """
    MCP tool: Extract program metadata including identification, specifications, software, and user context.

    This tool extracts test program information from STDF-V4 package test files
    with Intel CPU little-endian constraint enforcement.

    Args:
        file_path: Absolute path to STDF-V4 package test file

    Returns:
        Dict containing:
        - program_identification: Test program name, revision, and auxiliary files
        - specifications: Test specifications and flow information
        - tester_software: Executive software and tester details
        - user_context: User information and test context

    Raises:
        UnsupportedCPUArchitectureError: If file is not Intel CPU little-endian
        UnsupportedSTDFVersionError: If file is not STDF-V4
        UnsupportedTestScopeError: If file contains wafer test data
        InvalidSTDFFormatError: If file format is invalid
    """
    extractor = ProgramMetadataExtractor()
    return extractor.extract_program_metadata(file_path)


# For testing and debugging
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract STDF program metadata")
    parser.add_argument("file_path", help="Path to STDF file")
    args = parser.parse_args()

    try:
        result = extract_program_metadata(args.file_path)
        import json
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)