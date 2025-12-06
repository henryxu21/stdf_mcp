"""Test time extraction tool for STDF files.

This module provides the main extract_test_time() function for extracting
test execution times from STDF files and generating Excel reports with
statistical analysis.
"""

import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from stdf_mcp.stdf.parser import STDFV4Parser
from stdf_mcp.stdf.records.part_records import PIRRecord, PRRRecord
from stdf_mcp.tools.test_time.models import TestTimeWorkbook
from stdf_mcp.tools.test_time.validators import (
    validate_stdf_file_path,
    validate_site_numbers,
    validate_output_directory,
)
from stdf_mcp.tools.test_time.accumulator import DeviceTestTimeAccumulator
from stdf_mcp.tools.test_time.excel_generator import ExcelTestTimeGenerator
from stdf_mcp.tools.test_time.statistics import TestTimeStatisticsCalculator


def extract_test_time(
    stdf_file_path: str,
    site_num: Optional[List[int]] = None,
    output_directory: str = "/tmp",
) -> Dict[str, Any]:
    """Extract test execution times from STDF file to Excel with statistics.

    Processes STDF file PRR.TEST_T fields to extract test time for each device,
    generates Excel spreadsheet with columns (Device_ID, Site, Head, Timestamp,
    Test_Time), and calculates statistical metrics (min, max, mean, std dev).

    Args:
        stdf_file_path: Absolute path to STDF V4 file
        site_num: Optional list of site numbers [0-255] to filter. None = all sites.
        output_directory: Directory for Excel output. Defaults to /tmp.

    Returns:
        Dictionary containing:
            - excel_file_path: Path to generated Excel file
            - total_devices: Total device count (includes null test times)
            - valid_devices: Devices with valid test times
            - null_devices: Devices with missing test times (TEST_T=0)
            - min_seconds: Minimum test time (seconds)
            - max_seconds: Maximum test time (seconds)
            - mean_seconds: Mean test time (seconds)
            - std_dev_seconds: Population std dev (seconds)
            - extraction_time_seconds: Processing time (seconds)

    Raises:
        FileNotFoundError: If STDF file does not exist
        ValueError: If no PRR records found or invalid parameters
        OSError: If output directory not writable

    Example:
        >>> result = extract_test_time("/path/to/test.stdf")
        >>> print(f"Excel: {result['excel_file_path']}")
        >>> print(f"Mean time: {result['mean_seconds']:.3f}s")
    """
    start_time = time.time()

    try:
        # Validate inputs
        stdf_path = validate_stdf_file_path(stdf_file_path)
        validate_site_numbers(site_num)
        output_dir = validate_output_directory(output_directory)

        # Initialize components
        accumulator = DeviceTestTimeAccumulator(site_filter=site_num)
        parser = STDFV4Parser()

        # Parse STDF file and accumulate test time data
        # Note: parse_records() expects Path object, not file handle
        pir_count = 0
        prr_count = 0
        for record in parser.parse_records(stdf_path):
            if isinstance(record, PIRRecord):
                pir_count += 1
                accumulator.process_pir(record)
            elif isinstance(record, PRRRecord):
                prr_count += 1
                accumulator.process_prr(record)

        # Check if any PIR/PRR records were found
        if pir_count == 0 and prr_count == 0:
            raise ValueError(
                f"No PIR or PRR records found in STDF file. "
                f"Cannot extract test times. File may not contain device test data."
            )

        if pir_count == 0:
            raise ValueError(
                f"No PIR records found in STDF file (found {prr_count} PRR records). "
                f"PIR records are required to identify device start."
            )

        if prr_count == 0:
            raise ValueError(
                f"No PRR records found in STDF file (found {pir_count} PIR records). "
                f"PRR records contain the TEST_T field needed for test time extraction."
            )

        # Get accumulated records
        records = accumulator.get_records()

        if not records:
            # PRR records exist but all filtered out or no devices match criteria
            raise ValueError(
                f"No devices extracted. Found {pir_count} PIR and {prr_count} PRR records, "
                f"but no matching PIR/PRR pairs. "
                f"Site filter: {site_num if site_num else 'None (all sites)'}. "
                f"This may indicate PIR/PRR records are out of sync or filtered out."
            )

        # Calculate statistics
        calculator = TestTimeStatisticsCalculator()
        try:
            statistics = calculator.calculate_from_records(records)
        except ValueError as e:
            # All test times are None (all TEST_T=0)
            raise ValueError(
                f"No valid test times found. All devices have TEST_T=0. {e}"
            )

        # Generate Excel file
        timestamp = datetime.now()
        excel_generator = ExcelTestTimeGenerator()
        output_path = excel_generator.create_output_path(
            stdf_path, output_dir, timestamp
        )

        workbook = TestTimeWorkbook(
            records=records,
            statistics=statistics,
            stdf_file_path=stdf_path,
            extraction_time_seconds=0.0,  # Will update after Excel generation
            output_path=output_path,
        )

        excel_path = excel_generator.generate_excel(workbook)

        # Calculate total extraction time
        extraction_time = time.time() - start_time

        # Build result dictionary per outputSchema
        result = {
            "excel_file_path": str(excel_path),
            "total_devices": len(records),
            "valid_devices": statistics.device_count,
            "null_devices": statistics.null_count,
            "min_seconds": statistics.min_seconds,
            "max_seconds": statistics.max_seconds,
            "mean_seconds": statistics.mean_seconds,
            "std_dev_seconds": statistics.std_dev_seconds,
            "extraction_time_seconds": extraction_time,
        }

        return result

    except FileNotFoundError as e:
        # Re-raise FileNotFoundError as-is
        raise

    except ValueError as e:
        # Re-raise ValueError as-is
        raise

    except OSError as e:
        # Re-raise OSError for output directory issues
        raise

    except Exception as e:
        # Unexpected error - wrap with context
        raise RuntimeError(
            f"Unexpected error during test time extraction: {e}"
        ) from e
