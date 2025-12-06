"""
Automatic integrity validation for STDF-V4 files.

This module provides comprehensive integrity validation capabilities
for STDF-V4 files, including sequence validation, cross-reference
checking, and data consistency verification.
"""

from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from .records import (
    STDFV4Record, FARRecord, MIRRecord, MRRRecord,
    PIRRecord, PRRRecord, PTRRecord, FTRRecord,
    PCRRecord, HBRRecord, SBRRecord, TSRRecord
)
from .exceptions import (
    IntegrityValidationError,
    SequenceValidationError,
    CorruptedSTDFFileError
)


@dataclass
class ValidationResult:
    """Result of integrity validation."""

    is_valid: bool
    total_records: int = 0
    total_parts: int = 0
    total_tests: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SequenceTracker:
    """Tracks record sequences for validation."""

    far_seen: bool = False
    mir_seen: bool = False
    mrr_seen: bool = False
    current_parts: Dict[Tuple[int, int], PIRRecord] = field(default_factory=dict)  # (head, site) -> PIR
    completed_parts: List[PRRRecord] = field(default_factory=list)
    bin_counts: Dict[int, int] = field(default_factory=lambda: defaultdict(int))
    test_counts: Dict[int, int] = field(default_factory=lambda: defaultdict(int))


class IntegrityValidator:
    """
    Comprehensive integrity validator for STDF-V4 files.

    Performs validation of:
    - Record sequence integrity
    - Cross-record references
    - Mathematical consistency
    - Test result validation
    - Part flow validation
    """

    def __init__(self):
        """Initialize integrity validator."""
        self.sequence_tracker = SequenceTracker()
        self.validation_errors: List[str] = []
        self.validation_warnings: List[str] = []
        self.record_counts: Dict[str, int] = defaultdict(int)
        self.site_data: Dict[Tuple[int, int], Dict[str, Any]] = defaultdict(dict)

    def validate_records(self, records: List[STDFV4Record]) -> ValidationResult:
        """
        Validate list of STDF records for integrity.

        Args:
            records: List of STDF records to validate

        Returns:
            ValidationResult: Comprehensive validation result
        """
        self._reset_validation_state()

        # Process each record
        for i, record in enumerate(records):
            try:
                self._validate_single_record(record, i)
                self._update_sequence_tracking(record, i)
                self._count_record_types(record)
            except Exception as e:
                self.validation_errors.append(
                    f"Error processing record {i}: {e}"
                )

        # Perform cross-record validation
        self._validate_record_sequences()
        self._validate_part_flows()
        self._validate_bin_consistency()
        self._validate_test_coverage()

        # Generate statistics
        statistics = self._generate_statistics()

        return ValidationResult(
            is_valid=len(self.validation_errors) == 0,
            total_records=len(records),
            total_parts=len(self.sequence_tracker.completed_parts),
            total_tests=sum(self.record_counts.get(name, 0)
                          for name in ['PTR', 'FTR', 'MPR']),
            errors=self.validation_errors.copy(),
            warnings=self.validation_warnings.copy(),
            statistics=statistics
        )

    def _reset_validation_state(self) -> None:
        """Reset validator state for new validation."""
        self.sequence_tracker = SequenceTracker()
        self.validation_errors = []
        self.validation_warnings = []
        self.record_counts = defaultdict(int)
        self.site_data = defaultdict(dict)

    def _validate_single_record(self, record: STDFV4Record, index: int) -> None:
        """
        Validate individual record.

        Args:
            record: Record to validate
            index: Record index for error reporting
        """
        # Basic record validation
        if not record.is_valid_for_package_test():
            self.validation_errors.append(
                f"Record {index}: Invalid for package test context"
            )

        # Record-specific validation
        if isinstance(record, FARRecord):
            self._validate_far_record(record, index)
        elif isinstance(record, MIRRecord):
            self._validate_mir_record(record, index)
        elif isinstance(record, PIRRecord):
            self._validate_pir_record(record, index)
        elif isinstance(record, PRRRecord):
            self._validate_prr_record(record, index)
        elif isinstance(record, PTRRecord):
            self._validate_ptr_record(record, index)
        elif isinstance(record, FTRRecord):
            self._validate_ftr_record(record, index)

    def _validate_far_record(self, record: FARRecord, index: int) -> None:
        """Validate FAR record."""
        if not record.is_supported_version():
            self.validation_errors.append(
                f"Record {index}: Unsupported STDF version {record.stdf_ver}"
            )

        if index != 0:
            self.validation_errors.append(
                f"Record {index}: FAR record must be first record in file"
            )

    def _validate_mir_record(self, record: MIRRecord, index: int) -> None:
        """Validate MIR record."""
        if record.setup_t is None or record.start_t is None:
            self.validation_warnings.append(
                f"Record {index}: MIR missing required timestamps"
            )

    def _validate_pir_record(self, record: PIRRecord, index: int) -> None:
        """Validate PIR record."""
        site_key = (record.head_num, record.site_num)

        # Check for duplicate PIR without PRR
        if site_key in self.sequence_tracker.current_parts:
            self.validation_errors.append(
                f"Record {index}: Duplicate PIR for site {site_key} without PRR"
            )

    def _validate_prr_record(self, record: PRRRecord, index: int) -> None:
        """Validate PRR record."""
        site_key = (record.head_num, record.site_num)

        # Check for PRR without PIR
        if site_key not in self.sequence_tracker.current_parts:
            self.validation_errors.append(
                f"Record {index}: PRR without corresponding PIR for site {site_key}"
            )

        # Validate part flags
        if record.part_flg < 0 or record.part_flg > 255:
            self.validation_errors.append(
                f"Record {index}: Invalid part flag value {record.part_flg}"
            )

        # Validate bin numbers
        if record.hard_bin < 0 or record.hard_bin > 65535:
            self.validation_errors.append(
                f"Record {index}: Invalid hard bin number {record.hard_bin}"
            )

    def _validate_ptr_record(self, record: PTRRecord, index: int) -> None:
        """Validate PTR record."""
        site_key = (record.head_num, record.site_num)

        # Check for test without active part
        if site_key not in self.sequence_tracker.current_parts:
            self.validation_warnings.append(
                f"Record {index}: PTR test {record.test_num} without active PIR for site {site_key}"
            )

        # Validate test result vs limits
        if record.is_valid_result() and not record.is_within_limits():
            if record.is_passing():
                self.validation_warnings.append(
                    f"Record {index}: Test {record.test_num} marked as pass but outside limits"
                )

    def _validate_ftr_record(self, record: FTRRecord, index: int) -> None:
        """Validate FTR record."""
        site_key = (record.head_num, record.site_num)

        # Check for test without active part
        if site_key not in self.sequence_tracker.current_parts:
            self.validation_warnings.append(
                f"Record {index}: FTR test {record.test_num} without active PIR for site {site_key}"
            )

        # Validate failure count vs test flag
        failure_count = record.get_failure_count()
        if failure_count > 0 and record.is_passing():
            self.validation_warnings.append(
                f"Record {index}: Functional test {record.test_num} has failures but marked as pass"
            )

    def _update_sequence_tracking(self, record: STDFV4Record, index: int) -> None:
        """Update sequence tracking state."""
        if isinstance(record, FARRecord):
            self.sequence_tracker.far_seen = True

        elif isinstance(record, MIRRecord):
            self.sequence_tracker.mir_seen = True

        elif isinstance(record, MRRRecord):
            self.sequence_tracker.mrr_seen = True

        elif isinstance(record, PIRRecord):
            site_key = (record.head_num, record.site_num)
            self.sequence_tracker.current_parts[site_key] = record

        elif isinstance(record, PRRRecord):
            site_key = (record.head_num, record.site_num)
            if site_key in self.sequence_tracker.current_parts:
                del self.sequence_tracker.current_parts[site_key]
            self.sequence_tracker.completed_parts.append(record)
            self.sequence_tracker.bin_counts[record.hard_bin] += 1

        elif isinstance(record, (PTRRecord, FTRRecord)):
            self.sequence_tracker.test_counts[record.test_num] += 1

    def _count_record_types(self, record: STDFV4Record) -> None:
        """Count record types for statistics."""
        record_name = getattr(record, 'RECORD_NAME', 'Unknown')
        self.record_counts[record_name] += 1

    def _validate_record_sequences(self) -> None:
        """Validate overall record sequence integrity."""
        if not self.sequence_tracker.far_seen:
            self.validation_errors.append("Missing FAR record at start of file")

        if not self.sequence_tracker.mir_seen:
            self.validation_errors.append("Missing MIR record")

        # Check for incomplete parts (PIR without PRR)
        if self.sequence_tracker.current_parts:
            for site_key in self.sequence_tracker.current_parts:
                self.validation_errors.append(
                    f"Incomplete part sequence: PIR without PRR for site {site_key}"
                )

    def _validate_part_flows(self) -> None:
        """Validate part flow consistency."""
        # Group parts by site for analysis
        site_parts: Dict[Tuple[int, int], List[PRRRecord]] = defaultdict(list)
        for prr in self.sequence_tracker.completed_parts:
            site_key = (prr.head_num, prr.site_num)
            site_parts[site_key].append(prr)

        # Validate each site's part flow
        for site_key, parts in site_parts.items():
            self._validate_site_part_flow(site_key, parts)

    def _validate_site_part_flow(self, site_key: Tuple[int, int], parts: List[PRRRecord]) -> None:
        """Validate part flow for a specific site."""
        if not parts:
            return

        # Check for reasonable test counts
        test_counts = [part.num_test for part in parts if part.num_test is not None]
        if test_counts:
            avg_tests = sum(test_counts) / len(test_counts)
            for part in parts:
                if part.num_test is not None and abs(part.num_test - avg_tests) > avg_tests * 0.5:
                    self.validation_warnings.append(
                        f"Site {site_key}: Part with unusual test count {part.num_test} (avg: {avg_tests:.1f})"
                    )

    def _validate_bin_consistency(self) -> None:
        """Validate bin assignment consistency."""
        pass_bins = set()
        fail_bins = set()

        for prr in self.sequence_tracker.completed_parts:
            if prr.is_passing():
                pass_bins.add(prr.hard_bin)
            else:
                fail_bins.add(prr.hard_bin)

        # Check for bins used for both pass and fail
        overlap_bins = pass_bins & fail_bins
        if overlap_bins:
            self.validation_warnings.append(
                f"Hard bins used for both pass and fail: {sorted(overlap_bins)}"
            )

    def _validate_test_coverage(self) -> None:
        """Validate test coverage across parts."""
        if not self.sequence_tracker.completed_parts:
            return

        # Analyze test execution patterns
        parts_with_tests = sum(1 for prr in self.sequence_tracker.completed_parts
                             if prr.num_test and prr.num_test > 0)

        if parts_with_tests == 0:
            self.validation_warnings.append("No parts have recorded test counts")

    def _generate_statistics(self) -> Dict[str, Any]:
        """Generate comprehensive validation statistics."""
        total_parts = len(self.sequence_tracker.completed_parts)
        pass_parts = sum(1 for prr in self.sequence_tracker.completed_parts
                        if prr.is_passing())

        bin_stats = dict(self.sequence_tracker.bin_counts)
        test_stats = dict(self.sequence_tracker.test_counts)

        return {
            'record_counts': dict(self.record_counts),
            'total_parts': total_parts,
            'passing_parts': pass_parts,
            'failing_parts': total_parts - pass_parts,
            'yield_percent': (pass_parts / total_parts * 100) if total_parts > 0 else 0,
            'bin_counts': bin_stats,
            'test_counts': test_stats,
            'unique_bins': len(bin_stats),
            'unique_tests': len(test_stats),
            'validation_errors': len(self.validation_errors),
            'validation_warnings': len(self.validation_warnings)
        }

    def validate_file_integrity(self, records: List[STDFV4Record]) -> None:
        """
        Validate file-level integrity and raise exception if invalid.

        Args:
            records: List of STDF records

        Raises:
            IntegrityValidationError: If validation fails
        """
        result = self.validate_records(records)

        if not result.is_valid:
            raise IntegrityValidationError(
                result.errors
            )


def validate_stdf_integrity(records: List[STDFV4Record]) -> ValidationResult:
    """
    Convenience function to validate STDF record integrity.

    Args:
        records: List of STDF records

    Returns:
        ValidationResult: Validation result
    """
    validator = IntegrityValidator()
    return validator.validate_records(records)