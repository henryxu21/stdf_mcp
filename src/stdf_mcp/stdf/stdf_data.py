"""
Core STDF data model for structured representation.

This module provides high-level data structures for representing
parsed STDF data in a structured, analyzable format suitable
for MCP tool operations.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime
from pathlib import Path

from .records import (
    STDFV4Record, FARRecord, MIRRecord, MRRRecord,
    PIRRecord, PRRRecord, PTRRecord, FTRRecord, MPRRecord,
    PCRRecord, HBRRecord, SBRRecord, TSRRecord
)


@dataclass
class STDFFileMetadata:
    """Metadata about the STDF file itself."""

    file_path: Optional[Path] = None
    file_size: int = 0
    stdf_version: str = "V4"
    endianness: str = "little"
    cpu_type: Optional[str] = None
    creation_time: Optional[datetime] = None
    modification_time: Optional[datetime] = None
    record_count: int = 0
    parse_time_ms: int = 0
    integrity_validated: bool = False
    integrity_issues: List[str] = field(default_factory=list)


@dataclass
class TestSiteInfo:
    """Information about a test site."""

    head_num: int
    site_num: int
    site_description: Optional[str] = None
    total_parts_tested: int = 0
    passing_parts: int = 0
    failing_parts: int = 0
    retest_count: int = 0
    abort_count: int = 0


@dataclass
class TestDefinition:
    """Definition of a test including limits and metadata."""

    test_num: int
    test_name: Optional[str] = None
    test_type: str = "Unknown"  # Parametric, Functional, etc.
    units: Optional[str] = None
    low_limit: Optional[float] = None
    high_limit: Optional[float] = None
    low_spec: Optional[float] = None
    high_spec: Optional[float] = None
    test_description: Optional[str] = None
    execution_count: int = 0
    failure_count: int = 0
    alarm_count: int = 0


@dataclass
class TestResult:
    """Individual test result data."""

    test_num: int
    part_id: Optional[str] = None
    site_id: str = "0:0"  # head:site format
    result_value: Optional[float] = None
    test_flag: int = 0
    units: Optional[str] = None
    low_limit: Optional[float] = None
    high_limit: Optional[float] = None
    within_limits: bool = True
    passing: bool = True
    execution_time: Optional[float] = None


@dataclass
class PartResult:
    """Complete test results for a single part."""

    part_id: Optional[str] = None
    site_id: str = "0:0"
    head_num: int = 0
    site_num: int = 0
    part_flag: int = 0
    num_tests: int = 0
    hard_bin: int = 1
    soft_bin: Optional[int] = None
    x_coord: Optional[int] = None
    y_coord: Optional[int] = None
    test_time_ms: Optional[int] = None
    part_text: Optional[str] = None
    is_passing: bool = True
    test_results: List[TestResult] = field(default_factory=list)
    parametric_results: List[TestResult] = field(default_factory=list)
    functional_results: List[TestResult] = field(default_factory=list)


@dataclass
class BinDefinition:
    """Hardware or software bin definition."""

    bin_number: int
    bin_name: Optional[str] = None
    bin_type: str = "Unknown"  # Pass, Fail
    part_count: int = 0
    description: Optional[str] = None
    is_pass_bin: bool = False


@dataclass
class LotSummary:
    """Summary statistics for the entire lot."""

    lot_id: Optional[str] = None
    part_type: Optional[str] = None
    test_program: Optional[str] = None
    test_program_version: Optional[str] = None
    start_time: Optional[datetime] = None
    finish_time: Optional[datetime] = None
    total_parts: int = 0
    passing_parts: int = 0
    failing_parts: int = 0
    yield_percent: float = 0.0
    test_time_total_ms: int = 0
    test_time_avg_ms: float = 0.0
    unique_tests: int = 0
    sites_tested: List[TestSiteInfo] = field(default_factory=list)


@dataclass
class STDFData:
    """
    Complete STDF data structure.

    This is the main data container that holds all parsed and processed
    STDF information in a structured format suitable for analysis.
    """

    # File metadata
    file_metadata: STDFFileMetadata = field(default_factory=STDFFileMetadata)

    # Lot-level information
    lot_summary: LotSummary = field(default_factory=LotSummary)

    # Test site information
    test_sites: Dict[str, TestSiteInfo] = field(default_factory=dict)  # site_id -> info

    # Test definitions
    test_definitions: Dict[int, TestDefinition] = field(default_factory=dict)  # test_num -> def

    # Bin definitions
    hard_bins: Dict[int, BinDefinition] = field(default_factory=dict)  # bin_num -> def
    soft_bins: Dict[int, BinDefinition] = field(default_factory=dict)  # bin_num -> def

    # Part results
    part_results: List[PartResult] = field(default_factory=list)

    # Raw records (optional, for debugging)
    raw_records: Optional[List[STDFV4Record]] = None

    def get_site_id(self, head_num: int, site_num: int) -> str:
        """Generate site ID string from head and site numbers."""
        return f"{head_num}:{site_num}"

    def get_yield_by_site(self) -> Dict[str, float]:
        """Get yield percentage by test site."""
        yields = {}
        for site_id, site_info in self.test_sites.items():
            if site_info.total_parts_tested > 0:
                yields[site_id] = (site_info.passing_parts / site_info.total_parts_tested) * 100.0
            else:
                yields[site_id] = 0.0
        return yields

    def get_test_summary(self) -> Dict[str, Any]:
        """Get comprehensive test summary statistics."""
        total_tests = len(self.test_definitions)
        total_executions = sum(td.execution_count for td in self.test_definitions.values())
        total_failures = sum(td.failure_count for td in self.test_definitions.values())

        return {
            'total_unique_tests': total_tests,
            'total_test_executions': total_executions,
            'total_test_failures': total_failures,
            'test_pass_rate': ((total_executions - total_failures) / total_executions * 100.0)
                             if total_executions > 0 else 0.0,
            'parametric_tests': sum(1 for td in self.test_definitions.values()
                                  if td.test_type == 'Parametric'),
            'functional_tests': sum(1 for td in self.test_definitions.values()
                                  if td.test_type == 'Functional')
        }

    def get_bin_summary(self) -> Dict[str, Any]:
        """Get comprehensive bin summary statistics."""
        total_hard_bins = len(self.hard_bins)
        total_soft_bins = len(self.soft_bins)

        pass_bins = sum(1 for hb in self.hard_bins.values() if hb.is_pass_bin)
        fail_bins = total_hard_bins - pass_bins

        return {
            'total_hard_bins': total_hard_bins,
            'total_soft_bins': total_soft_bins,
            'pass_hard_bins': pass_bins,
            'fail_hard_bins': fail_bins,
            'bin_utilization': len([hb for hb in self.hard_bins.values() if hb.part_count > 0])
        }

    def get_parts_by_bin(self, bin_number: int) -> List[PartResult]:
        """Get all parts that went to a specific hard bin."""
        return [part for part in self.part_results if part.hard_bin == bin_number]

    def get_failing_tests(self, min_failure_rate: float = 0.1) -> List[TestDefinition]:
        """Get tests with failure rate above threshold."""
        failing_tests = []
        for test_def in self.test_definitions.values():
            if test_def.execution_count > 0:
                failure_rate = test_def.failure_count / test_def.execution_count
                if failure_rate >= min_failure_rate:
                    failing_tests.append(test_def)

        return sorted(failing_tests, key=lambda t: t.failure_count, reverse=True)

    def get_test_results_for_test(self, test_num: int) -> List[TestResult]:
        """Get all test results for a specific test number."""
        results = []
        for part in self.part_results:
            for test_result in part.test_results:
                if test_result.test_num == test_num:
                    results.append(test_result)
        return results

    def get_statistics_summary(self) -> Dict[str, Any]:
        """Get comprehensive statistics summary."""
        return {
            'file_info': {
                'path': str(self.file_metadata.file_path) if self.file_metadata.file_path else None,
                'size_bytes': self.file_metadata.file_size,
                'record_count': self.file_metadata.record_count,
                'parse_time_ms': self.file_metadata.parse_time_ms,
                'integrity_validated': self.file_metadata.integrity_validated
            },
            'lot_summary': {
                'lot_id': self.lot_summary.lot_id,
                'part_type': self.lot_summary.part_type,
                'total_parts': self.lot_summary.total_parts,
                'yield_percent': self.lot_summary.yield_percent,
                'test_time_avg_ms': self.lot_summary.test_time_avg_ms
            },
            'test_summary': self.get_test_summary(),
            'bin_summary': self.get_bin_summary(),
            'site_yields': self.get_yield_by_site()
        }

    def filter_parts_by_criteria(self,
                                passing: Optional[bool] = None,
                                hard_bin: Optional[int] = None,
                                site_id: Optional[str] = None,
                                min_test_time: Optional[int] = None,
                                max_test_time: Optional[int] = None) -> List[PartResult]:
        """
        Filter parts by various criteria.

        Args:
            passing: Filter by pass/fail status
            hard_bin: Filter by hard bin number
            site_id: Filter by site ID
            min_test_time: Minimum test time in ms
            max_test_time: Maximum test time in ms

        Returns:
            List[PartResult]: Filtered parts
        """
        filtered_parts = self.part_results

        if passing is not None:
            filtered_parts = [p for p in filtered_parts if p.is_passing == passing]

        if hard_bin is not None:
            filtered_parts = [p for p in filtered_parts if p.hard_bin == hard_bin]

        if site_id is not None:
            filtered_parts = [p for p in filtered_parts if p.site_id == site_id]

        if min_test_time is not None:
            filtered_parts = [p for p in filtered_parts
                            if p.test_time_ms is not None and p.test_time_ms >= min_test_time]

        if max_test_time is not None:
            filtered_parts = [p for p in filtered_parts
                            if p.test_time_ms is not None and p.test_time_ms <= max_test_time]

        return filtered_parts

    def to_dict(self) -> Dict[str, Any]:
        """Convert STDF data to dictionary for JSON serialization."""
        # Convert to dictionary, handling dataclass serialization
        def serialize_dataclass(obj):
            if hasattr(obj, '__dataclass_fields__'):
                result = {}
                for field_name in obj.__dataclass_fields__:
                    value = getattr(obj, field_name)
                    if value is not None:
                        if isinstance(value, datetime):
                            result[field_name] = value.isoformat()
                        elif isinstance(value, Path):
                            result[field_name] = str(value)
                        elif isinstance(value, dict):
                            result[field_name] = {k: serialize_dataclass(v) for k, v in value.items()}
                        elif isinstance(value, list):
                            result[field_name] = [serialize_dataclass(v) for v in value]
                        else:
                            result[field_name] = value
                return result
            else:
                return obj

        return serialize_dataclass(self)