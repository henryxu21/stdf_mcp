"""
MCP Tool Entry Point for Filtered Test Data Extraction.

This module provides the main extract_filtered_data function that serves as the
MCP tool entry point for filtering STDF test data and generating column-based Excel output.
"""

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from stdf_mcp.stdf.parser import STDFV4Parser
from stdf_mcp.stdf.records.part_records import PIRRecord, PRRRecord
from stdf_mcp.stdf.records.test_records import PTRRecord
from stdf_mcp.tools.filtered_data.device_accumulator import (
    MultiSiteDeviceAccumulator,
)
from stdf_mcp.tools.filtered_data.excel_generator import ExcelGenerator
from stdf_mcp.tools.filtered_data.filter_engine import FilterEngine
from stdf_mcp.tools.filtered_data.models import (
    DeviceTestResults,
    ExcelWorkbook,
    ExcelWorksheet,
    FilterCriteria,
    TestNumFilter,
    TestParameter,
    TestSuiteFilter,
)
from stdf_mcp.tools.filtered_data.validators import (
    validate_filter_criteria,
    validate_output_directory,
    validate_regex_pattern,
    validate_site_numbers,
    validate_test_num_input,
)

# Configure logging for this module
logger = logging.getLogger(__name__)


def extract_filtered_data(
    stdf_file_path: str,
    test_name: Optional[str] = None,
    test_num: Optional[List[Union[int, str]]] = None,
    test_suite_name: Optional[str] = None,
    is_suite_qualified: bool = False,
    site_num: Optional[List[int]] = None,
    output_directory: str = "/tmp",
) -> Dict[str, Any]:
    """
    Extract filtered test data from STDF file to column-based Excel file.

    Supports filtering by test suite name (simple or qualified) using TSR hierarchy.

    Args:
        stdf_file_path: Absolute path to STDF-V4 file
        test_name: Optional test parameter name filter (regex pattern)
        test_num: Optional test number filter (single/series/range)
        test_suite_name: Optional test suite name filter (simple or qualified)
        is_suite_qualified: If True, treat test_suite_name as fully qualified path
        site_num: Optional site number filter (single/multiple)
        output_directory: Absolute path to output directory

    Returns:
        dict: MCP tool output with excel_file_path and metadata
            {
                "excel_file_path": str,
                "total_devices_matched": int,
                "total_test_parameters": int,
                "total_columns": int,
                "total_rows": int,
                "test_parameters": List[Dict],
                "extraction_time_seconds": float,
                "test_suite_name": str | null,
                "test_suite_qualified_path": str | null
            }

    Raises:
        ValueError: Invalid input parameters, no matching data, or mutual exclusivity violation
        FileNotFoundError: STDF file or output directory not found

    Examples:
        # Filter by test name regex
        extract_filtered_data("file.stdf", test_name="VDD_.*")

        # Filter by test suite simple name
        extract_filtered_data("file.stdf", test_suite_name="Bt5gRxIp2")

        # Filter by fully qualified suite name
        extract_filtered_data("file.stdf", test_suite_name="Main.RxIp2.Bt5gRxIp2",
                            is_suite_qualified=True)
    """
    start_time = time.time()

    # Input validation
    if not stdf_file_path:
        raise ValueError("stdf_file_path is required")

    stdf_path = Path(stdf_file_path)
    if not stdf_path.exists():
        raise FileNotFoundError(f"STDF file not found: {stdf_file_path}")

    output_dir = Path(output_directory)
    validate_output_directory(output_dir)

    # T014: Mutual exclusivity validation
    active_filters = sum([
        test_name is not None,
        test_num is not None,
        test_suite_name is not None
    ])

    if active_filters == 0:
        raise ValueError(
            "Must specify one filter: test_name, test_num, or test_suite_name"
        )

    if active_filters > 1:
        raise ValueError(
            "test_suite_name, test_name, and test_num are mutually exclusive. "
            "Provide exactly one filter criterion."
        )

    # Parse filter criteria
    test_name_pattern = None
    test_num_filter = None
    test_suite_resolved_path = None

    # T015: Add TSR parsing logic when test_suite_name provided
    if test_suite_name:
        from stdf_mcp.stdf.records.summary_records import TSRRecord
        from stdf_mcp.tools.filtered_data.hierarchy import HierarchyMap

        # Parse TSR records and build HierarchyMap
        parser = STDFV4Parser()
        tsr_records = []

        for record in parser.parse_records(stdf_path):
            if isinstance(record, TSRRecord):
                tsr_records.append(record)

        # T016: Check for TSR presence
        if not tsr_records:
            raise ValueError(
                "Test suite filtering requires TSR records, but none found in STDF file. "
                "Use test_name or test_num filtering instead."
            )

        logger.info(f"Found {len(tsr_records)} TSR records for hierarchy parsing")

        # Build HierarchyMap and get test numbers
        hierarchy_map = HierarchyMap.from_tsr_records(tsr_records)

        suite_filter = TestSuiteFilter(
            suite_name=test_suite_name,
            is_qualified=is_suite_qualified,
            case_sensitive=False,
            site_filter=site_num
        )

        matched_test_nums = hierarchy_map.get_test_numbers_for_suite(suite_filter)

        if not matched_test_nums:
            raise ValueError(
                f"No matching test suite found for name '{test_suite_name}'. "
                f"Please verify the suite name exists in the STDF file."
            )

        logger.info(
            f"Matched suite '{test_suite_name}': {len(matched_test_nums)} test numbers"
        )

        # Convert to TestNumFilter for existing pipeline
        test_num_filter = TestNumFilter(series_set=matched_test_nums, ranges=[])

        # Get resolved qualified path for output
        matched_suites = hierarchy_map.get_test_suite(
            test_suite_name,
            is_suite_qualified,
            case_sensitive=False
        )
        if matched_suites:
            test_suite_resolved_path = matched_suites[0].qualified_path

    elif test_name:
        test_name_pattern = validate_regex_pattern(test_name)

    elif test_num:
        validate_test_num_input(test_num)
        test_num_filter = TestNumFilter.from_input(test_num)

    # Validate site filter
    if site_num is not None:
        validate_site_numbers(site_num)

    # Create FilterCriteria
    filter_criteria = FilterCriteria(
        test_name_pattern=test_name_pattern,
        test_num_filter=test_num_filter,
        site_filter=site_num,
        output_directory=output_dir,
    )

    # Validate filter criteria
    validate_filter_criteria(
        test_name_pattern, test_num_filter, site_num, output_dir
    )

    logger.info(
        f"Starting filtered data extraction: file={stdf_path.name}, "
        f"test_name={test_name}, test_num={test_num}, site_num={site_num}"
    )

    # Two-pass STDF processing (T026)
    parser = STDFV4Parser()

    # Pass 1: Determine filtered parameters
    filtered_parameters = _determine_filtered_parameters(
        parser, stdf_path, filter_criteria
    )

    logger.info(
        f"Pass 1 complete: {len(filtered_parameters)} test parameters matched filter"
    )

    # Check for no matching data (T032)
    if not filtered_parameters:
        raise ValueError(
            "NO_MATCHING_DATA: No test parameters matched the filter criteria. "
            "Please check your test_name pattern or test_num values."
        )

    # Pass 2: Accumulate device data
    device_rows = _accumulate_device_data(
        parser, stdf_path, filter_criteria, filtered_parameters
    )

    logger.info(
        f"Pass 2 complete: {len(device_rows)} devices matched filter"
    )

    # Check for no device data (T032)
    if not device_rows:
        raise ValueError(
            "NO_MATCHING_DATA: No devices matched the filter criteria. "
            "Please check your site_num filter or verify the STDF file contains test data."
        )

    # Create Excel worksheet
    worksheet = ExcelWorksheet(
        common_columns=["Device_ID", "Site", "Head", "Timestamp"],
        test_parameters=filtered_parameters,
        device_rows=device_rows,
    )

    # Create Excel workbook
    extraction_time = time.time() - start_time
    workbook = ExcelWorkbook(
        worksheet=worksheet,
        filter_criteria=filter_criteria,
        stdf_file_path=stdf_path,
        extraction_time_seconds=extraction_time,
        timestamp=datetime.now(),
    )

    # Generate Excel file
    generator = ExcelGenerator()
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    stdf_filename = stdf_path.stem
    excel_filename = f"{stdf_filename}_FilteredData_{timestamp_str}.xlsx"
    excel_path = output_dir / excel_filename

    generator.generate_workbook(workbook, excel_path)

    logger.info(
        f"Excel file generated: {excel_filename} "
        f"({worksheet.total_rows} rows × {worksheet.total_columns} columns) "
        f"in {extraction_time:.2f}s"
    )

    # Prepare output
    test_params_list = [
        {
            "test_name": param.test_name,
            "test_number": param.test_number,
            "units": param.units,
        }
        for param in filtered_parameters
    ]

    # T017: Update return dict to include test_suite fields
    return {
        "excel_file_path": str(excel_path),
        "total_devices_matched": workbook.total_parts_matched,
        "total_test_parameters": workbook.total_test_columns,
        "total_columns": worksheet.total_columns,
        "total_rows": worksheet.total_rows,
        "test_parameters": test_params_list,
        "extraction_time_seconds": round(extraction_time, 2),
        "test_suite_name": test_suite_name,
        "test_suite_qualified_path": test_suite_resolved_path,
    }


def _determine_filtered_parameters(
    parser: STDFV4Parser, stdf_path: Path, criteria: FilterCriteria
) -> List[TestParameter]:
    """
    Pass 1: Scan STDF file to determine which test parameters match filter.

    Args:
        parser: STDF parser instance
        stdf_path: Path to STDF file
        criteria: Filter criteria

    Returns:
        List of TestParameter objects for matching tests (ordered by test_num)
    """
    # Collect all test parameters from PTR records
    all_parameters: Dict[int, TestParameter] = {}

    for record in parser.parse_records(stdf_path):
        if isinstance(record, PTRRecord):
            test_num = record.test_num
            test_name = record.test_txt or f"TestNum_{test_num}"

            # Create TestParameter if not already seen
            if test_num not in all_parameters:
                all_parameters[test_num] = TestParameter(
                    test_name=test_name,
                    test_number=test_num,
                    units=getattr(record, "units", None),
                    lo_limit=getattr(record, "lo_limit", None),
                    hi_limit=getattr(record, "hi_limit", None),
                )

    # Convert to list and apply filter
    all_params_list = list(all_parameters.values())

    # Apply filter using FilterEngine
    filter_engine = FilterEngine()
    filtered = filter_engine.get_filtered_parameters(
        all_params_list,
        test_name_pattern=criteria.test_name_pattern,
        test_num_filter=criteria.test_num_filter,
    )

    # Sort by test_num for consistent column ordering
    filtered.sort(key=lambda p: p.test_number)

    return filtered


def _accumulate_device_data(
    parser: STDFV4Parser,
    stdf_path: Path,
    criteria: FilterCriteria,
    filtered_parameters: List[TestParameter],
) -> List[DeviceTestResults]:
    """
    Pass 2: Accumulate test results using MultiSiteDeviceAccumulator.

    CRITICAL: Uses site-keyed tracking to handle parallel multi-site testing.
    Each PIR creates a NEW device entry (row in Excel), not grouped by
    (device_id, site) across the entire file.

    Pattern: For 10 DUTs × 2 sites = 20 rows expected, not 2 rows.

    Args:
        parser: STDF parser instance
        stdf_path: Path to STDF file
        criteria: Filter criteria
        filtered_parameters: List of test parameters to extract

    Returns:
        List of DeviceTestResults (one per part) in chronological order
    """
    # Create parameter name set for fast lookup
    param_names = {p.test_name for p in filtered_parameters}

    # Initialize MultiSiteDeviceAccumulator with filtered parameter names
    accumulator = MultiSiteDeviceAccumulator(param_names)

    # Initialize FilterEngine for site filtering
    filter_engine = FilterEngine()

    # Process STDF records in PIR→PTR→PRR sequence
    for record in parser.parse_records(stdf_path):
        if isinstance(record, PIRRecord):
            # PIR: Start new device context for this site
            site = record.site_num

            # Apply site filter to PIR
            if not filter_engine.matches_site(site, criteria.site_filter):
                continue  # Skip this PIR (device from filtered site)

            device_id = str(getattr(record, "part_id", "Unknown"))
            head = record.head_num
            timestamp = None  # PIR doesn't have timestamp in STDF-V4

            accumulator.process_pir(device_id, site, head, timestamp)

        elif isinstance(record, PTRRecord):
            # PTR: Add test result to device matching PTR's site
            ptr_site = record.site_num

            # Apply site filter using FilterEngine
            if not filter_engine.matches_site(ptr_site, criteria.site_filter):
                continue  # Skip this PTR

            test_num = record.test_num
            test_name = record.test_txt or f"TestNum_{test_num}"
            test_result = record.result

            # process_ptr will check if test_name is in filtered_params
            accumulator.process_ptr(ptr_site, test_name, test_result)

        elif isinstance(record, PRRRecord):
            # PRR: Finalize device matching PRR's site
            prr_site = record.site_num

            # Apply site filter to PRR
            if not filter_engine.matches_site(prr_site, criteria.site_filter):
                continue  # Skip this PRR

            # Extract part_id from PRR (fixes device ID extraction - FR-001)
            part_id = record.part_id if record.part_id else ""

            accumulator.process_prr(prr_site, part_id)

    # Get all completed devices in chronological order
    device_results = accumulator.get_completed_devices()

    return device_results
