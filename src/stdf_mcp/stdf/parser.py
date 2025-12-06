"""
Intel CPU Little-Endian STDF-V4 streaming parser implementation.

This module provides a streaming parser for STDF-V4 files that can handle
large files efficiently while maintaining memory constraints. It validates
file format for Intel CPU little-endian only, enforces package test scope,
and provides automatic integrity validation.

CONSTRAINT: Only supports Intel CPU little-endian STDF-V4 files (CPU_TYP=1).
All big-endian and non-Intel CPU architectures are explicitly rejected.
"""

import os
import struct
from pathlib import Path
from typing import BinaryIO, Iterator, Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field

from .types import (
    CPUType, STDFVersion,
    is_package_test_record, is_wafer_test_record,
    STDFConstants
)
from .exceptions import (
    InvalidSTDFFormatError,
    UnsupportedSTDFVersionError,
    UnsupportedCPUArchitectureError,
    UnsupportedTestScopeError,
    CorruptedSTDFFileError,
    FileSizeExceededError,
    MemoryLimitExceededError,
    SequenceValidationError,
    RecordParsingError
)
from .records import STDFV4Record, RecordFactory, FARRecord


@dataclass
class ParserConfig:
    """Configuration options for Intel CPU little-endian STDF-V4 parser."""

    max_file_size_mb: int = 1024  # Maximum file size in MB
    enable_integrity_validation: bool = True
    package_test_only: bool = True
    max_memory_usage_mb: int = 512  # Maximum memory usage during parsing
    streaming_buffer_size: int = 65536  # Buffer size for streaming reads
    validate_record_sequence: bool = True
    # Note: strict_endianness_check removed - only Intel CPU little-endian supported


@dataclass
class ParseResult:
    """Result of parsing operations with metadata."""

    success: bool
    records_parsed: int = 0
    file_size: int = 0
    parse_time_ms: int = 0
    # Note: endianness field removed - always Intel CPU little-endian
    stdf_version: Optional[str] = None
    integrity_issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    error_message: Optional[str] = None


@dataclass
class FileValidationResult:
    """Result of file validation operations."""

    is_valid: bool
    stdf_version: str
    # Note: endianness field removed - always Intel CPU little-endian
    file_size: int
    estimated_record_count: Optional[int] = None
    validation_issues: List[str] = field(default_factory=list)


class STDFV4Parser:
    """
    Streaming Intel CPU little-endian STDF-V4 parser with validation and integrity checking.

    This parser enforces strict STDF-V4 compliance, Intel CPU little-endian format,
    and package test scope. It provides streaming access to records for memory-efficient
    processing of large files.

    CONSTRAINT: Only supports Intel CPU little-endian STDF-V4 files (CPU_TYP=1).
    """

    def __init__(self, config: Optional[ParserConfig] = None):
        """
        Initialize Intel CPU little-endian STDF-V4 parser with configuration.

        Args:
            config: Parser configuration options
        """
        self.config = config or ParserConfig()
        self._current_file: Optional[BinaryIO] = None
        # Note: _current_endianness removed - always Intel CPU little-endian
        self._records_parsed = 0
        self._integrity_issues: List[str] = []
        self._sequence_state: Dict[str, Any] = {}

    @property
    def max_file_size_mb(self) -> int:
        """Get maximum file size limit in MB."""
        return self.config.max_file_size_mb

    @property
    def enable_integrity_validation(self) -> bool:
        """Get integrity validation status."""
        return self.config.enable_integrity_validation

    @property
    def package_test_only(self) -> bool:
        """Get package test only enforcement status."""
        return self.config.package_test_only

    def validate_stdf_format(self, file_path: Path) -> Tuple[bool, str]:
        """
        Validate STDF file format and version.

        Args:
            file_path: Path to STDF file

        Returns:
            Tuple[bool, str]: (is_valid, version)

        Raises:
            InvalidSTDFFormatError: If file is not valid STDF format
            UnsupportedSTDFVersionError: If STDF version is not supported
            CorruptedSTDFFileError: If file is corrupted
        """
        if not file_path.exists():
            raise InvalidSTDFFormatError(
                f"File does not exist: {file_path}",
                str(file_path)
            )

        file_size = file_path.stat().st_size
        if file_size > self.config.max_file_size_mb * 1024 * 1024:
            raise FileSizeExceededError(
                file_size, self.config.max_file_size_mb * 1024 * 1024,
                str(file_path)
            )

        if file_size < STDFConstants.MIN_FILE_SIZE:
            raise InvalidSTDFFormatError(
                f"File too small to be valid STDF: {file_size} bytes",
                str(file_path)
            )

        try:
            with open(file_path, 'rb') as f:
                # Read first record (should be FAR)
                header_data = f.read(STDFConstants.RECORD_HEADER_SIZE)
                if len(header_data) < STDFConstants.RECORD_HEADER_SIZE:
                    raise CorruptedSTDFFileError(
                        "Insufficient data for record header",
                        str(file_path), 0
                    )

                # Try to parse record header with both endiannesses to detect format
                endianness = None
                rec_len = rec_typ = rec_sub = None

                # Try little-endian first (Intel CPU)
                try:
                    rec_len_le, rec_typ_le, rec_sub_le = struct.unpack('<HBB', header_data)
                    # Valid FAR record with reasonable length (FAR should be 2 bytes)
                    if (rec_typ_le == 0 and rec_sub_le == 10 and
                        1 <= rec_len_le <= 10):  # FAR record length should be small
                        endianness = 'little'
                        rec_len, rec_typ, rec_sub = rec_len_le, rec_typ_le, rec_sub_le
                except struct.error:
                    pass

                # Try big-endian if little-endian failed or doesn't look reasonable
                if endianness is None:
                    try:
                        rec_len_be, rec_typ_be, rec_sub_be = struct.unpack('>HBB', header_data)
                        # Valid FAR record with reasonable length
                        if (rec_typ_be == 0 and rec_sub_be == 10 and
                            1 <= rec_len_be <= 10):  # FAR record length should be small
                            endianness = 'big'
                            rec_len, rec_typ, rec_sub = rec_len_be, rec_typ_be, rec_sub_be
                    except struct.error:
                        pass

                # If neither worked, it's not a valid STDF file
                if endianness is None:
                    raise InvalidSTDFFormatError(
                        f"First record is not FAR: invalid header data",
                        str(file_path)
                    )

                # Validate this is FAR record
                if rec_typ != 0 or rec_sub != 10:
                    raise InvalidSTDFFormatError(
                        f"First record is not FAR: type={rec_typ}, subtype={rec_sub}",
                        str(file_path)
                    )

                # Read FAR record data
                if rec_len < 2:
                    raise CorruptedSTDFFileError(
                        f"Invalid FAR record length: {rec_len}",
                        str(file_path), STDFConstants.RECORD_HEADER_SIZE
                    )

                far_data = f.read(rec_len)
                if len(far_data) < rec_len:
                    raise CorruptedSTDFFileError(
                        "Truncated FAR record",
                        str(file_path), STDFConstants.RECORD_HEADER_SIZE
                    )

                # Parse FAR record to get CPU type and STDF version using detected endianness
                endian_char = '<' if endianness == 'little' else '>'
                cpu_type, stdf_ver = struct.unpack(f'{endian_char}BB', far_data[:2])

                # Validate Intel-compatible CPU architecture (CPU_TYP=1 or CPU_TYP=2) - reject all others
                if cpu_type not in (CPUType.VAX, CPUType.INTEL_X86):
                    raise UnsupportedCPUArchitectureError(
                        f"Non-Intel CPU architecture not supported: CPU_TYP={cpu_type}. "
                        f"Only Intel-compatible little-endian (CPU_TYP=1,2) files are supported.",
                        cpu_type
                    )

                # Validate STDF version
                if stdf_ver != STDFVersion.V4:
                    if stdf_ver == STDFVersion.V3:
                        raise UnsupportedSTDFVersionError("V3", str(file_path))
                    else:
                        raise UnsupportedSTDFVersionError(f"V{stdf_ver}", str(file_path))

                return True, "V4"

        except (OSError, struct.error) as e:
            raise CorruptedSTDFFileError(
                f"Error reading file: {e}",
                str(file_path)
            )

    def detect_endianness(self, file_path: Path) -> str:
        """
        Detect file endianness from FAR record.

        Args:
            file_path: Path to STDF file

        Returns:
            str: 'little' or 'big'

        Raises:
            CorruptedSTDFFileError: If cannot determine endianness
            EndiannessMismatchError: If endianness is inconsistent
        """
        try:
            with open(file_path, 'rb') as f:
                # Skip record header, read FAR data
                f.seek(STDFConstants.RECORD_HEADER_SIZE)
                far_data = f.read(2)

                if len(far_data) < 2:
                    raise CorruptedSTDFFileError(
                        "Cannot read FAR record for endianness detection",
                        str(file_path)
                    )

                cpu_type = far_data[0]

                # Both VAX (CPU_TYP=1) and Intel x86 (CPU_TYP=2) are little-endian
                if cpu_type in (CPUType.VAX, CPUType.INTEL_X86):
                    return "little"
                elif cpu_type == CPUType.SUN_SPARC:
                    return "big"
                else:
                    raise CorruptedSTDFFileError(
                        f"Unknown CPU type for endianness: {cpu_type}",
                        str(file_path)
                    )

        except OSError as e:
            raise CorruptedSTDFFileError(
                f"Error detecting endianness: {e}",
                str(file_path)
            )

    def validate_package_test_scope(self, file_path: Path) -> bool:
        """
        Validate file contains only package test data.

        Args:
            file_path: Path to STDF file

        Returns:
            bool: True if package test scope is valid

        Raises:
            UnsupportedTestScopeError: If wafer test records found
        """
        if not self.config.package_test_only:
            return True

        try:
            # Sample first several records to check for wafer test indicators
            with open(file_path, 'rb') as f:
                endianness = self.detect_endianness(file_path)

                records_checked = 0
                max_records_to_check = 100  # Reasonable sample size

                f.seek(0)  # Start from beginning

                while records_checked < max_records_to_check:
                    # Read record header
                    header_data = f.read(STDFConstants.RECORD_HEADER_SIZE)
                    if len(header_data) < STDFConstants.RECORD_HEADER_SIZE:
                        break  # End of file

                    rec_len, rec_typ, rec_sub = STDFV4Record.parse_header(header_data)

                    # Check for wafer test records
                    if is_wafer_test_record(rec_typ, rec_sub):
                        raise UnsupportedTestScopeError(
                            "wafer test", str(file_path)
                        )

                    # Skip record data
                    f.seek(rec_len, 1)
                    records_checked += 1

                return True

        except (OSError, struct.error) as e:
            raise CorruptedSTDFFileError(
                f"Error validating test scope: {e}",
                str(file_path)
            )

    def get_struct_format(self, endian: str, format_string: str) -> str:
        """
        Create complete struct format string with endianness.

        Args:
            endian: Endianness ('little' or 'big')
            format_string: Base format string

        Returns:
            str: Complete format string
        """
        endian_char = '<' if endian == 'little' else '>'
        return endian_char + format_string

    def parse_records(self, file_path: Path) -> Iterator[STDFV4Record]:
        """
        Parse STDF file and yield records in streaming fashion.

        Args:
            file_path: Path to STDF file

        Yields:
            STDFV4Record: Parsed STDF records

        Raises:
            Various STDF exceptions for validation and parsing errors
        """
        # Validate file first
        self.validate_stdf_format(file_path)
        endianness = self.detect_endianness(file_path)
        self.validate_package_test_scope(file_path)

        self._current_endianness = endianness
        self._records_parsed = 0
        self._integrity_issues = []

        try:
            with open(file_path, 'rb') as f:
                self._current_file = f
                position = 0

                while True:
                    # Read record header
                    header_data = f.read(STDFConstants.RECORD_HEADER_SIZE)
                    if len(header_data) < STDFConstants.RECORD_HEADER_SIZE:
                        break  # End of file

                    try:
                        rec_len, rec_typ, rec_sub = STDFV4Record.parse_header(header_data)

                        # Validate record length
                        if rec_len > STDFConstants.MAX_RECORD_LENGTH:
                            raise CorruptedSTDFFileError(
                                f"Invalid record length: {rec_len}",
                                str(file_path), position
                            )

                        # Read record data
                        record_data = f.read(rec_len)
                        if len(record_data) < rec_len:
                            raise CorruptedSTDFFileError(
                                f"Truncated record at position {position}",
                                str(file_path), position
                            )

                        # Create record instance (Intel CPU little-endian only)
                        record = RecordFactory.create_record(
                            rec_typ, rec_sub, record_data, position
                        )

                        # Perform integrity validation if enabled
                        if self.config.enable_integrity_validation:
                            self._validate_record_integrity(record, position)

                        # Update position and counters
                        position += STDFConstants.RECORD_HEADER_SIZE + rec_len
                        self._records_parsed += 1

                        yield record

                    except RecordParsingError as e:
                        # Skip corrupted records but continue parsing
                        if rec_len > 0:
                            f.seek(rec_len, 1)
                            position += STDFConstants.RECORD_HEADER_SIZE + rec_len
                        else:
                            position += STDFConstants.RECORD_HEADER_SIZE

                        self._integrity_issues.append(str(e))
                        continue

        except OSError as e:
            raise CorruptedSTDFFileError(
                f"Error reading file: {e}",
                str(file_path)
            )
        finally:
            self._current_file = None

    def _validate_record_integrity(self, record: STDFV4Record, position: int) -> None:
        """
        Validate record integrity and sequence.

        Args:
            record: Record to validate
            position: File position of record
        """
        # Basic record validation
        if not record.is_valid_for_package_test():
            self._integrity_issues.append(
                f"Record at position {position} not valid for package test"
            )

        # Sequence validation (basic implementation)
        if self.config.validate_record_sequence:
            self._validate_record_sequence(record, position)

    def _validate_record_sequence(self, record: STDFV4Record, position: int) -> None:
        """
        Validate record appears in correct sequence.

        Args:
            record: Record to validate
            position: File position of record
        """
        # Simple sequence validation - can be extended
        if self._records_parsed == 0:
            # First record must be FAR
            if not isinstance(record, FARRecord):
                self._integrity_issues.append(
                    f"First record is not FAR at position {position}"
                )

    def get_file_validation_summary(self, file_path: Path) -> FileValidationResult:
        """
        Get comprehensive file validation summary.

        Args:
            file_path: Path to STDF file

        Returns:
            FileValidationResult: Validation summary
        """
        try:
            # Basic validation
            is_valid, version = self.validate_stdf_format(file_path)
            endianness = self.detect_endianness(file_path)
            is_package_scope = self.validate_package_test_scope(file_path)

            file_size = file_path.stat().st_size

            # Estimate record count (rough approximation)
            avg_record_size = 50  # Rough average
            estimated_records = file_size // avg_record_size

            return FileValidationResult(
                is_valid=is_valid and is_package_scope,
                stdf_version=version,
                endianness=endianness,
                file_size=file_size,
                estimated_record_count=estimated_records,
                validation_issues=[]
            )

        except Exception as e:
            return FileValidationResult(
                is_valid=False,
                stdf_version="Unknown",
                endianness="Unknown",
                file_size=0,
                validation_issues=[str(e)]
            )

    def get_integrity_issues(self) -> List[str]:
        """Get list of integrity issues found during parsing."""
        return self._integrity_issues.copy()

    def get_records_parsed_count(self) -> int:
        """Get number of records parsed in last operation."""
        return self._records_parsed