"""
STDF-V4 data conversion utilities.

This module provides conversion between parsed STDF records and
structured data models, including builders for constructing
complete STDFData structures from streaming record input.
"""

from typing import List, Dict, Optional, Any, Tuple
from pathlib import Path
from datetime import datetime
import time

from .records import (
    STDFV4Record, FARRecord, MIRRecord, MRRRecord,
    PIRRecord, PRRRecord, PTRRecord, FTRRecord, MPRRecord,
    PCRRecord, HBRRecord, SBRRecord, TSRRecord
)
from .stdf_data import (
    STDFData, STDFFileMetadata, LotSummary, TestSiteInfo,
    TestDefinition, TestResult, PartResult, BinDefinition
)
from .parser import STDFV4Parser, ParserConfig
from .integrity import IntegrityValidator, ValidationResult
from .exceptions import STDFError


class STDFDataBuilder:
    """
    Builder for constructing STDFData from streaming records.

    Processes records in streaming fashion and builds comprehensive
    data structures suitable for analysis and MCP tool operations.
    """

    def __init__(self):
        """Initialize data builder."""
        self.stdf_data = STDFData()
        self._current_parts: Dict[str, PartResult] = {}  # site_id -> active part
        self._test_executions: Dict[int, int] = {}  # test_num -> execution count
        self._test_failures: Dict[int, int] = {}   # test_num -> failure count
        self._start_time = None
        self._record_count = 0

    def process_record(self, record: STDFV4Record) -> None:
        """
        Process a single STDF record and update data structures.

        Args:
            record: STDF record to process
        """
        self._record_count += 1

        # Process based on record type
        if isinstance(record, FARRecord):
            self._process_far_record(record)
        elif isinstance(record, MIRRecord):
            self._process_mir_record(record)
        elif isinstance(record, MRRRecord):
            self._process_mrr_record(record)
        elif isinstance(record, PIRRecord):
            self._process_pir_record(record)
        elif isinstance(record, PRRRecord):
            self._process_prr_record(record)
        elif isinstance(record, PTRRecord):
            self._process_ptr_record(record)
        elif isinstance(record, FTRRecord):
            self._process_ftr_record(record)
        elif isinstance(record, MPRRecord):
            self._process_mpr_record(record)
        elif isinstance(record, PCRRecord):
            self._process_pcr_record(record)
        elif isinstance(record, HBRRecord):
            self._process_hbr_record(record)
        elif isinstance(record, SBRRecord):
            self._process_sbr_record(record)
        elif isinstance(record, TSRRecord):
            self._process_tsr_record(record)

    def _process_far_record(self, record: FARRecord) -> None:
        """Process File Attribute Record."""
        self.stdf_data.file_metadata.stdf_version = record.get_stdf_version_name()
        self.stdf_data.file_metadata.endianness = record.get_endianness()
        self.stdf_data.file_metadata.cpu_type = record.get_cpu_type_name()

    def _process_mir_record(self, record: MIRRecord) -> None:
        """Process Master Information Record."""
        self.stdf_data.lot_summary.lot_id = record.lot_id
        self.stdf_data.lot_summary.part_type = record.part_typ
        self.stdf_data.lot_summary.test_program = record.job_nam
        self.stdf_data.lot_summary.test_program_version = record.job_rev

        if record.start_t:
            self.stdf_data.lot_summary.start_time = record.get_start_time()

    def _process_mrr_record(self, record: MRRRecord) -> None:
        """Process Master Results Record."""
        if record.finish_t:
            self.stdf_data.lot_summary.finish_time = record.get_finish_time()

    def _process_pir_record(self, record: PIRRecord) -> None:
        """Process Part Information Record."""
        site_id = self.stdf_data.get_site_id(record.head_num, record.site_num)

        # Create new part result
        part_result = PartResult(
            site_id=site_id,
            head_num=record.head_num,
            site_num=record.site_num
        )

        # Store as current part for this site
        self._current_parts[site_id] = part_result

        # Update site info
        if site_id not in self.stdf_data.test_sites:
            self.stdf_data.test_sites[site_id] = TestSiteInfo(
                head_num=record.head_num,
                site_num=record.site_num
            )

    def _process_prr_record(self, record: PRRRecord) -> None:
        """Process Part Results Record."""
        site_id = self.stdf_data.get_site_id(record.head_num, record.site_num)

        # Get current part for this site
        if site_id not in self._current_parts:
            # Create part if PIR was missing
            part_result = PartResult(
                site_id=site_id,
                head_num=record.head_num,
                site_num=record.site_num
            )
        else:
            part_result = self._current_parts[site_id]

        # Update part with PRR data
        part_result.part_id = record.part_id
        part_result.part_flag = record.part_flg
        part_result.num_tests = record.num_test
        part_result.hard_bin = record.hard_bin
        part_result.soft_bin = record.soft_bin
        part_result.x_coord = record.x_coord
        part_result.y_coord = record.y_coord
        part_result.test_time_ms = record.test_t
        part_result.part_text = record.part_txt
        part_result.is_passing = record.is_passing()

        # Add to completed parts
        self.stdf_data.part_results.append(part_result)

        # Update lot summary
        self.stdf_data.lot_summary.total_parts += 1
        if part_result.is_passing:
            self.stdf_data.lot_summary.passing_parts += 1
        else:
            self.stdf_data.lot_summary.failing_parts += 1

        # Update site statistics
        site_info = self.stdf_data.test_sites[site_id]
        site_info.total_parts_tested += 1
        if part_result.is_passing:
            site_info.passing_parts += 1
        else:
            site_info.failing_parts += 1

        # Update bin counts
        if record.hard_bin not in self.stdf_data.hard_bins:
            self.stdf_data.hard_bins[record.hard_bin] = BinDefinition(
                bin_number=record.hard_bin,
                is_pass_bin=record.is_passing()
            )
        self.stdf_data.hard_bins[record.hard_bin].part_count += 1

        # Clean up current parts
        if site_id in self._current_parts:
            del self._current_parts[site_id]

    def _process_ptr_record(self, record: PTRRecord) -> None:
        """Process Parametric Test Record."""
        site_id = self.stdf_data.get_site_id(record.head_num, record.site_num)

        # Create test result
        test_result = TestResult(
            test_num=record.test_num,
            part_id=None,  # Will be filled by PRR
            site_id=site_id,
            result_value=record.get_scaled_result(),
            test_flag=record.test_flg,
            units=record.units,
            low_limit=record.lo_limit,
            high_limit=record.hi_limit,
            within_limits=record.is_within_limits(),
            passing=record.is_passing()
        )

        # Add to current part if exists
        if site_id in self._current_parts:
            self._current_parts[site_id].test_results.append(test_result)
            self._current_parts[site_id].parametric_results.append(test_result)

        # Update test definition
        if record.test_num not in self.stdf_data.test_definitions:
            self.stdf_data.test_definitions[record.test_num] = TestDefinition(
                test_num=record.test_num,
                test_name=record.test_txt,
                test_type="Parametric",
                units=record.units,
                low_limit=record.lo_limit,
                high_limit=record.hi_limit
            )

        # Update execution counts
        test_def = self.stdf_data.test_definitions[record.test_num]
        test_def.execution_count += 1
        if not record.is_passing():
            test_def.failure_count += 1

        self.stdf_data.lot_summary.unique_tests = len(self.stdf_data.test_definitions)

    def _process_ftr_record(self, record: FTRRecord) -> None:
        """Process Functional Test Record."""
        site_id = self.stdf_data.get_site_id(record.head_num, record.site_num)

        # Create test result
        test_result = TestResult(
            test_num=record.test_num,
            site_id=site_id,
            test_flag=record.test_flg,
            passing=record.is_passing()
        )

        # Add to current part if exists
        if site_id in self._current_parts:
            self._current_parts[site_id].test_results.append(test_result)
            self._current_parts[site_id].functional_results.append(test_result)

        # Update test definition
        if record.test_num not in self.stdf_data.test_definitions:
            self.stdf_data.test_definitions[record.test_num] = TestDefinition(
                test_num=record.test_num,
                test_name=record.test_txt or f"Functional_Test_{record.test_num}",
                test_type="Functional"
            )

        # Update execution counts
        test_def = self.stdf_data.test_definitions[record.test_num]
        test_def.execution_count += 1
        if not record.is_passing():
            test_def.failure_count += 1

    def _process_mpr_record(self, record: MPRRecord) -> None:
        """Process Multiple-Result Parametric Record."""
        site_id = self.stdf_data.get_site_id(record.head_num, record.site_num)

        # Create test definition if needed
        if record.test_num not in self.stdf_data.test_definitions:
            self.stdf_data.test_definitions[record.test_num] = TestDefinition(
                test_num=record.test_num,
                test_name=record.test_txt or f"MPR_Test_{record.test_num}",
                test_type="Multiple_Parametric",
                units=record.units
            )

        # Update execution counts
        test_def = self.stdf_data.test_definitions[record.test_num]
        test_def.execution_count += 1
        if not record.is_passing():
            test_def.failure_count += 1

    def _process_pcr_record(self, record: PCRRecord) -> None:
        """Process Part Count Record."""
        site_id = self.stdf_data.get_site_id(record.head_num, record.site_num)

        if site_id in self.stdf_data.test_sites:
            site_info = self.stdf_data.test_sites[site_id]
            site_info.total_parts_tested = record.part_cnt
            site_info.passing_parts = record.good_cnt or 0
            site_info.retest_count = record.rtst_cnt or 0
            site_info.abort_count = record.abrt_cnt or 0

    def _process_hbr_record(self, record: HBRRecord) -> None:
        """Process Hardware Bin Record."""
        if record.hbin_num not in self.stdf_data.hard_bins:
            self.stdf_data.hard_bins[record.hbin_num] = BinDefinition(
                bin_number=record.hbin_num,
                bin_name=record.hbin_nam,
                is_pass_bin=record.is_pass_bin(),
                bin_type="Pass" if record.is_pass_bin() else "Fail"
            )

        bin_def = self.stdf_data.hard_bins[record.hbin_num]
        bin_def.part_count = record.hbin_cnt
        if record.hbin_nam:
            bin_def.bin_name = record.hbin_nam

    def _process_sbr_record(self, record: SBRRecord) -> None:
        """Process Software Bin Record."""
        if record.sbin_num not in self.stdf_data.soft_bins:
            self.stdf_data.soft_bins[record.sbin_num] = BinDefinition(
                bin_number=record.sbin_num,
                bin_name=record.sbin_nam,
                is_pass_bin=record.is_pass_bin(),
                bin_type="Pass" if record.is_pass_bin() else "Fail"
            )

        bin_def = self.stdf_data.soft_bins[record.sbin_num]
        bin_def.part_count = record.sbin_cnt

    def _process_tsr_record(self, record: TSRRecord) -> None:
        """Process Test Synopsis Record."""
        if record.test_num in self.stdf_data.test_definitions:
            test_def = self.stdf_data.test_definitions[record.test_num]
            if record.test_nam:
                test_def.test_name = record.test_nam
            if record.exec_cnt is not None:
                test_def.execution_count = record.exec_cnt
            if record.fail_cnt is not None:
                test_def.failure_count = record.fail_cnt

    def finalize(self, file_path: Optional[Path] = None,
                parse_time_ms: int = 0) -> STDFData:
        """
        Finalize data construction and calculate summary statistics.

        Args:
            file_path: Path to source STDF file
            parse_time_ms: Time taken to parse file

        Returns:
            STDFData: Complete STDF data structure
        """
        # Set file metadata
        if file_path:
            self.stdf_data.file_metadata.file_path = file_path
            self.stdf_data.file_metadata.file_size = file_path.stat().st_size
            self.stdf_data.file_metadata.creation_time = datetime.fromtimestamp(
                file_path.stat().st_ctime
            )
            self.stdf_data.file_metadata.modification_time = datetime.fromtimestamp(
                file_path.stat().st_mtime
            )

        self.stdf_data.file_metadata.record_count = self._record_count
        self.stdf_data.file_metadata.parse_time_ms = parse_time_ms

        # Calculate yield percentage
        if self.stdf_data.lot_summary.total_parts > 0:
            self.stdf_data.lot_summary.yield_percent = (
                self.stdf_data.lot_summary.passing_parts /
                self.stdf_data.lot_summary.total_parts * 100.0
            )

        # Calculate average test time
        test_times = [part.test_time_ms for part in self.stdf_data.part_results
                     if part.test_time_ms is not None]
        if test_times:
            self.stdf_data.lot_summary.test_time_avg_ms = sum(test_times) / len(test_times)
            self.stdf_data.lot_summary.test_time_total_ms = sum(test_times)

        return self.stdf_data


class STDFConverter:
    """
    High-level converter for transforming STDF files to structured data.

    Provides convenient methods for parsing STDF files and converting
    them to STDFData structures suitable for MCP tool operations.
    """

    def __init__(self, parser_config: Optional[ParserConfig] = None):
        """
        Initialize STDF converter.

        Args:
            parser_config: Parser configuration options
        """
        self.parser_config = parser_config or ParserConfig()
        self.parser = STDFV4Parser(self.parser_config)

    def convert_file(self, file_path: Path,
                    validate_integrity: bool = True) -> STDFData:
        """
        Convert STDF file to structured data format.

        Args:
            file_path: Path to STDF file
            validate_integrity: Perform integrity validation

        Returns:
            STDFData: Complete structured data

        Raises:
            STDFError: If file processing fails
        """
        start_time = time.time()

        try:
            # Initialize builder
            builder = STDFDataBuilder()

            # Process records in streaming fashion
            record_count = 0
            for record in self.parser.parse_records(file_path):
                builder.process_record(record)
                record_count += 1

            # Finalize data structure
            parse_time_ms = int((time.time() - start_time) * 1000)
            stdf_data = builder.finalize(file_path, parse_time_ms)

            # Perform integrity validation if requested
            if validate_integrity:
                validator = IntegrityValidator()
                validation_result = validator.validate_records(stdf_data.part_results)

                stdf_data.file_metadata.integrity_validated = validation_result.is_valid
                stdf_data.file_metadata.integrity_issues = validation_result.errors

            return stdf_data

        except Exception as e:
            if isinstance(e, STDFError):
                raise
            else:
                raise STDFError(f"File conversion failed: {e}", str(file_path))

    def convert_records(self, records: List[STDFV4Record],
                       file_path: Optional[Path] = None) -> STDFData:
        """
        Convert list of STDF records to structured data format.

        Args:
            records: List of STDF records
            file_path: Optional source file path

        Returns:
            STDFData: Complete structured data
        """
        start_time = time.time()

        # Initialize builder
        builder = STDFDataBuilder()

        # Process all records
        for record in records:
            builder.process_record(record)

        # Finalize data structure
        parse_time_ms = int((time.time() - start_time) * 1000)
        return builder.finalize(file_path, parse_time_ms)

    def validate_and_convert(self, file_path: Path) -> Tuple[STDFData, ValidationResult]:
        """
        Validate file and convert to structured data.

        Args:
            file_path: Path to STDF file

        Returns:
            Tuple[STDFData, ValidationResult]: Data and validation results
        """
        # Convert file
        stdf_data = self.convert_file(file_path, validate_integrity=False)

        # Perform separate validation
        validator = IntegrityValidator()
        validation_result = validator.validate_records(stdf_data.part_results)

        # Update metadata
        stdf_data.file_metadata.integrity_validated = validation_result.is_valid
        stdf_data.file_metadata.integrity_issues = validation_result.errors

        return stdf_data, validation_result

    def get_file_summary(self, file_path: Path) -> Dict[str, Any]:
        """
        Get quick file summary without full conversion.

        Args:
            file_path: Path to STDF file

        Returns:
            Dict[str, Any]: File summary information
        """
        try:
            # Get validation summary
            validation_result = self.parser.get_file_validation_summary(file_path)

            return {
                "file_path": str(file_path),
                "file_size": validation_result.file_size,
                "stdf_version": validation_result.stdf_version,
                "endianness": validation_result.endianness,
                "estimated_records": validation_result.estimated_record_count,
                "is_valid": validation_result.is_valid,
                "validation_issues": validation_result.validation_issues
            }

        except Exception as e:
            return {
                "file_path": str(file_path),
                "error": str(e),
                "is_valid": False
            }


# Convenience functions
def convert_stdf_file(file_path: Path,
                     validate_integrity: bool = True) -> STDFData:
    """
    Convenience function to convert STDF file to structured data.

    Args:
        file_path: Path to STDF file
        validate_integrity: Perform integrity validation

    Returns:
        STDFData: Complete structured data
    """
    converter = STDFConverter()
    return converter.convert_file(file_path, validate_integrity)


def get_stdf_file_summary(file_path: Path) -> Dict[str, Any]:
    """
    Convenience function to get STDF file summary.

    Args:
        file_path: Path to STDF file

    Returns:
        Dict[str, Any]: File summary information
    """
    converter = STDFConverter()
    return converter.get_file_summary(file_path)