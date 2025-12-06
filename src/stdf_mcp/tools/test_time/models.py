"""Data models for test time analysis.

This module defines the core data structures for extracting and analyzing
test execution times from STDF files.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional


@dataclass
class TestTimeRecord:
    """Test execution time data for a single device.

    Represents the test time extracted from a single device's PRR record,
    along with identification information from the PIR record.

    Attributes:
        device_id: Device identifier from PIR.PART_ID
        site: Test site number from PIR.SITE_NUM (0-255)
        head: Test head number from PIR.HEAD_NUM (0-255)
        timestamp: Test timestamp (always None - PIR lacks timestamps in STDF V4)
        test_time_seconds: PRR.TEST_T converted to seconds, None if TEST_T=0
    """

    device_id: str
    site: int
    head: int
    timestamp: Optional[datetime]
    test_time_seconds: Optional[float]

    def __post_init__(self) -> None:
        """Validate field constraints."""
        if not self.device_id:
            raise ValueError("device_id cannot be empty")
        if not 0 <= self.site <= 255:
            raise ValueError(f"site must be 0-255, got {self.site}")
        if not 0 <= self.head <= 255:
            raise ValueError(f"head must be 0-255, got {self.head}")
        if self.test_time_seconds is not None and self.test_time_seconds < 0:
            raise ValueError(
                f"test_time_seconds must be ≥0, got {self.test_time_seconds}"
            )


@dataclass
class TestTimeStatistics:
    """Statistical metrics for test execution times.

    Aggregated statistics calculated across all devices with valid test times.
    Uses population standard deviation (÷N formula) since STDF contains
    complete population of tested devices.

    Attributes:
        min_seconds: Minimum test time across all valid devices
        max_seconds: Maximum test time across all valid devices
        mean_seconds: Arithmetic mean (average) test time
        std_dev_seconds: Population standard deviation (σ = sqrt(Σ(xi-μ)²/N))
        device_count: Total devices with valid (non-null) test times
        null_count: Count of devices with missing TEST_T (TEST_T=0)
    """

    min_seconds: float
    max_seconds: float
    mean_seconds: float
    std_dev_seconds: float
    device_count: int
    null_count: int

    def __post_init__(self) -> None:
        """Validate statistical constraints."""
        if self.min_seconds > self.max_seconds:
            raise ValueError(
                f"min {self.min_seconds} > max {self.max_seconds}"
            )
        if self.std_dev_seconds < 0:
            raise ValueError(
                f"std_dev cannot be negative: {self.std_dev_seconds}"
            )
        if self.device_count <= 0:
            raise ValueError(
                f"device_count must be >0, got {self.device_count}"
            )
        if self.null_count < 0:
            raise ValueError(
                f"null_count must be ≥0, got {self.null_count}"
            )


@dataclass
class TestTimeWorkbook:
    """Container for Excel workbook generation.

    Combines test time records with metadata needed for Excel file generation
    and MCP tool response.

    Attributes:
        records: List of device test time records
        statistics: Calculated statistics matching records
        stdf_file_path: Source STDF file path
        extraction_time_seconds: Time taken to extract data
        output_path: Generated Excel file path
    """

    records: List[TestTimeRecord]
    statistics: TestTimeStatistics
    stdf_file_path: Path
    extraction_time_seconds: float
    output_path: Path

    def __post_init__(self) -> None:
        """Validate workbook consistency."""
        if not self.records:
            raise ValueError("records list cannot be empty")

        # Validate statistics match records
        valid_count = sum(
            1 for r in self.records if r.test_time_seconds is not None
        )
        if self.statistics.device_count != valid_count:
            raise ValueError(
                f"statistics.device_count {self.statistics.device_count} "
                f"!= actual valid records {valid_count}"
            )

        if not self.stdf_file_path.exists():
            raise ValueError(f"STDF file not found: {self.stdf_file_path}")

        if not self.output_path.parent.exists():
            raise ValueError(
                f"Output directory not found: {self.output_path.parent}"
            )
