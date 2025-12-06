"""Per-unit yield extraction from STDF files.

This module provides functions to extract pass/fail yield data from STDF files
and generate CSV output with PART_ID, PorF, HW Bin, SW Bin columns.
"""

import csv
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict


class YieldRecord(TypedDict):
    """Single unit yield data record for CSV output.

    Note: PorF column removed due to unreliable PART_FLG programming by vendors.
    Users can infer Pass/Fail from bin assignments (typically HW Bin 1 = Pass).

    Attributes:
        PART_ID: Sequential unit number (1-indexed)
        HW_Bin: Hardware bin number or "N/A"
        SW_Bin: Software bin number or "N/A"
    """

    PART_ID: str
    HW_Bin: str
    SW_Bin: str


def determine_pass_fail(part_flg: int) -> str:
    """Determine Pass/Fail from PART_FLG bitfield.

    STDF-V4 Specification PART_FLG bits (per existing PRRRecord.is_passing()):
    - Bit 0 (0x01): Pass/Fail status ← PRIMARY P/F indicator (0=Pass, 1=Fail)
    - Bit 1 (0x02): Part tested (0=tested, 1=not tested)
    - Bit 2 (0x04): Abnormal test
    - Bit 3 (0x08): Failed during test execution
    - Bit 4 (0x10): No electrical contact
    - Bit 5-7: Reserved

    Args:
        part_flg: PART_FLG byte from PRR record

    Returns:
        "Pass" if bit 0 is 0, "Fail" if bit 0 is 1
    """
    FAIL_BIT_MASK = 0x01  # Bit 0: Primary pass/fail indicator
    return "Fail" if (part_flg & FAIL_BIT_MASK) else "Pass"


def format_bin_value(bin_value: Optional[int]) -> str:
    """Format bin value for CSV output.

    Args:
        bin_value: Bin number from PRR (None if missing)

    Returns:
        String representation: "N/A" if None, otherwise str(bin_value)
    """
    return "N/A" if bin_value is None else str(bin_value)


def generate_output_filename(stdf_filename: str) -> str:
    """Generate output CSV filename following naming convention.

    Format: <STDF_file_name>_YieldAnalysis_<TimeStamp>.csv
    TimeStamp: YYYYMMDD_HHMMSS (ISO 8601 compact format, local time)

    Args:
        stdf_filename: Original STDF filename (e.g., "test_results.stdf")

    Returns:
        CSV filename (e.g., "test_results_YieldAnalysis_20251106_143022.csv")
    """
    base_name = Path(stdf_filename).stem  # Remove extension
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base_name}_YieldAnalysis_{timestamp}.csv"


def ensure_output_directory() -> Path:
    """Ensure TestCases/Output/ directory exists and is writable.

    Returns:
        Path object for output directory

    Raises:
        PermissionError: If directory not writable
        OSError: If directory creation fails
    """
    output_dir = Path("TestCases/Output")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Verify writable
    if not os.access(output_dir, os.W_OK):
        raise PermissionError(
            f"Output directory {output_dir} is not writable. "
            "Check file permissions."
        )

    return output_dir


def validate_and_extract_prr(stdf_path: str) -> List[Any]:
    """Validate STDF file and extract all PRR records.

    Args:
        stdf_path: Path to STDF file

    Returns:
        List of PRR records

    Raises:
        FileNotFoundError: If file doesn't exist
        RecordParsingError: If file is invalid/corrupted
        ValueError: If no PRR records found
    """
    from stdf_mcp.stdf.parser import STDFV4Parser
    from stdf_mcp.stdf.records.part_records import PRRRecord

    # Validate file exists (parser will handle this, but explicit check)
    if not Path(stdf_path).exists():
        raise FileNotFoundError(f"STDF file '{stdf_path}' not found")

    # Parse STDF file and extract PRR records
    parser = STDFV4Parser()
    prr_records = []

    for record in parser.parse_records(Path(stdf_path)):
        if isinstance(record, PRRRecord):
            prr_records.append(record)

    # Validate at least one PRR record exists
    if not prr_records:
        raise ValueError(
            f"No PRR records found in {stdf_path}. "
            "File may not contain test results."
        )

    return prr_records


def transform_prr_to_yield(prr_records: List[Any]) -> List[YieldRecord]:
    """Transform PRR records to YieldRecord format.

    Args:
        prr_records: List of PRR records from STDF file

    Returns:
        List of YieldRecord dictionaries with PART_ID, HW_Bin, SW_Bin
    """
    yield_records: List[YieldRecord] = []

    for index, prr in enumerate(prr_records, start=1):
        # Generate sequential PART_ID (1-indexed)
        part_id = str(index)

        # Format bin values (None → "N/A")
        hw_bin = format_bin_value(prr.hard_bin)
        sw_bin = format_bin_value(prr.soft_bin)

        # Create YieldRecord (PorF removed due to unreliable vendor programming)
        yield_record: YieldRecord = {
            "PART_ID": part_id,
            "HW_Bin": hw_bin,
            "SW_Bin": sw_bin,
        }

        yield_records.append(yield_record)

    return yield_records


def write_yield_csv(
    output_path: str, yield_records: List[YieldRecord]
) -> None:
    """Write yield records to CSV file.

    Args:
        output_path: Path to output CSV file
        yield_records: List of YieldRecord dictionaries

    Raises:
        OSError: If file cannot be written
    """
    # Column order per specification (3 columns: PART_ID, HW Bin, SW Bin)
    fieldnames = ["PART_ID", "HW Bin", "SW Bin"]

    # Transform records to match CSV header field names (spaces instead of underscores)
    csv_rows = []
    for record in yield_records:
        csv_row = {
            "PART_ID": record["PART_ID"],
            "HW Bin": record["HW_Bin"],
            "SW Bin": record["SW_Bin"],
        }
        csv_rows.append(csv_row)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)


def extract_per_unit_yield(
    stdf_file_path: str, output_directory: str = "TestCases/Output"
) -> Dict[str, Any]:
    """Extract per-unit yield data from STDF file to CSV.

    Main entry point for yield extraction. Processes STDF file, extracts
    PRR records, transforms to yield format, and writes CSV output.

    Note: PorF column removed due to unreliable PART_FLG programming by vendors.
    Users can infer Pass/Fail from bin assignments (typically HW Bin 1 = Pass).

    Args:
        stdf_file_path: Path to input STDF file
        output_directory: Directory for output CSV (default: TestCases/Output)

    Returns:
        Success dict with keys:
            - success (bool): True if extraction succeeded
            - csv_file_path (str): Absolute path to generated CSV
            - units_processed (int): Number of units extracted
            - processing_time_ms (int): Processing time in milliseconds

        Error dict with keys:
            - success (bool): False
            - error_code (str): Error category code
            - error_message (str): Human-readable error description

    Raises:
        No exceptions raised - all errors returned in error dict
    """
    start_time = time.time()

    try:
        # Step 1: Validate and extract PRR records
        prr_records = validate_and_extract_prr(stdf_file_path)

        # Step 2: Transform PRR records to YieldRecord format
        yield_records = transform_prr_to_yield(prr_records)

        # Step 3: Ensure output directory exists
        output_dir = Path(output_directory)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Verify writable
        if not os.access(output_dir, os.W_OK):
            raise PermissionError(
                f"Output directory {output_dir} is not writable. "
                "Check file permissions."
            )

        # Step 4: Generate output filename
        stdf_filename = Path(stdf_file_path).name
        csv_filename = generate_output_filename(stdf_filename)
        csv_path = output_dir / csv_filename

        # Step 5: Write CSV file
        write_yield_csv(str(csv_path), yield_records)

        # Step 6: Calculate statistics
        units_processed = len(yield_records)

        # Step 7: Calculate processing time
        end_time = time.time()
        processing_time_ms = int((end_time - start_time) * 1000)

        # Return success result per MCP contract (PorF stats removed)
        return {
            "success": True,
            "csv_file_path": str(csv_path.absolute()),
            "units_processed": units_processed,
            "processing_time_ms": processing_time_ms,
        }

    except FileNotFoundError as e:
        return {
            "success": False,
            "error_code": "FILE_NOT_FOUND",
            "error_message": str(e),
        }

    except ValueError as e:
        # Covers NO_PRR_RECORDS case
        return {
            "success": False,
            "error_code": "NO_PRR_RECORDS",
            "error_message": str(e),
        }

    except PermissionError as e:
        return {
            "success": False,
            "error_code": "PERMISSION_DENIED",
            "error_message": str(e),
        }

    except OSError as e:
        return {
            "success": False,
            "error_code": "OUTPUT_DIR_ERROR",
            "error_message": f"Failed to create or write to output directory: {e}",
        }

    except Exception as e:
        # Check if it's a corrupted STDF file error
        error_str = str(e)
        if (
            "Truncated" in error_str
            or "Corrupted" in error_str
            or "Invalid" in error_str
        ):
            return {
                "success": False,
                "error_code": "INVALID_STDF_FORMAT",
                "error_message": f"STDF file appears to be corrupted or invalid: {e}",
            }

        # Catch-all for unexpected errors
        return {
            "success": False,
            "error_code": "PROCESSING_ERROR",
            "error_message": f"Unexpected error during yield extraction: {e}",
        }
