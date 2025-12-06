"""
Base STDF-V4 record class and common functionality.

This module provides the base class for all STDF-V4 record types,
including common parsing functionality, validation methods, and
data structure management for package test contexts.
"""

import struct
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, ClassVar
from pathlib import Path

from ..exceptions import (
    RecordParsingError,
    UnsupportedRecordTypeError,
    CorruptedSTDFFileError
)
from ..types import (
    CPUType,
    RecordType,
    RecordSubtype,
    is_package_test_record,
    is_wafer_test_record,
    is_priority_record,
    is_non_priority_record,
    get_record_tier,
    get_endian_format,
    STDF_DATA_TYPES,
    STDFConstants
)


@dataclass
class STDFV4Record(ABC):
    """
    Base class for all STDF-V4 record types.

    This abstract base class provides common functionality for parsing,
    validation, and data management across all STDF record types,
    with specific focus on package test validation.
    """

    # Common fields for all records
    record_type: int
    record_subtype: int
    record_length: int
    file_position: int

    # Class-level constants (to be overridden by subclasses)
    RECORD_TYPE: ClassVar[int]
    RECORD_SUBTYPE: ClassVar[int]
    RECORD_NAME: ClassVar[str]

    @classmethod
    @abstractmethod
    def parse(cls, data: bytes, position: int) -> 'STDFV4Record':
        """
        Parse binary data into record object (Intel CPU little-endian only).

        Args:
            data: Binary record data (without header)
            position: File position where record starts

        Returns:
            STDFV4Record: Parsed record instance

        Raises:
            RecordParsingError: If parsing fails
        """
        pass

    @classmethod
    def identify_record_type(cls, header_data: bytes) -> Tuple[int, int]:
        """
        Identify record type and subtype from header.

        Args:
            header_data: First 4 bytes of record (REC_LEN + REC_TYP + REC_SUB)

        Returns:
            Tuple[int, int]: Record type and subtype

        Raises:
            CorruptedSTDFFileError: If header is invalid
        """
        if len(header_data) < 4:
            raise CorruptedSTDFFileError(
                f"Invalid record header length: {len(header_data)} bytes"
            )

        try:
            # Parse header: REC_LEN(2) + REC_TYP(1) + REC_SUB(1)
            # Only use first 4 bytes even if more data is provided
            rec_len, rec_typ, rec_sub = struct.unpack('<HBB', header_data[:4])
            return rec_typ, rec_sub
        except struct.error as e:
            raise CorruptedSTDFFileError(f"Failed to parse record header: {e}")

    @classmethod
    def validate_package_test_context(cls, record_data: bytes) -> bool:
        """
        Validate this record is appropriate for package test context.

        Args:
            record_data: Complete record data including header

        Returns:
            bool: True if record is valid for package test

        Raises:
            UnsupportedRecordTypeError: If record is wafer test specific
        """
        if len(record_data) < 4:
            return False

        rec_typ, rec_sub = cls.identify_record_type(record_data[:4])

        # Check if this is a wafer test record (explicitly rejected)
        if is_wafer_test_record(rec_typ, rec_sub):
            raise UnsupportedRecordTypeError(
                rec_typ, rec_sub,
                "Wafer test records are not supported. "
                "Only package/final test data is supported."
            )

        # Check if this is a valid package test record
        return is_package_test_record(rec_typ, rec_sub)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert record to dictionary for JSON serialization.

        Returns:
            Dict[str, Any]: Record data as dictionary
        """
        # Use dataclass asdict functionality but exclude None values
        result = {}
        for field_name in self.__dataclass_fields__:
            value = getattr(self, field_name)
            if value is not None:
                result[field_name] = value
        return result

    def get_record_info(self) -> Dict[str, Any]:
        """
        Get basic record information.

        Returns:
            Dict[str, Any]: Record metadata
        """
        return {
            'record_type': self.record_type,
            'record_subtype': self.record_subtype,
            'record_name': getattr(self, 'RECORD_NAME', 'Unknown'),
            'record_length': self.record_length,
            'file_position': self.file_position
        }

    @staticmethod
    def parse_header(data: bytes) -> Tuple[int, int, int]:
        """
        Parse STDF record header (Intel CPU little-endian format only).

        Args:
            data: Binary data starting with record header

        Returns:
            Tuple[int, int, int]: Record length, type, and subtype

        Raises:
            CorruptedSTDFFileError: If header parsing fails
        """
        if len(data) < STDFConstants.RECORD_HEADER_SIZE:
            raise CorruptedSTDFFileError(
                f"Insufficient data for record header: {len(data)} bytes"
            )

        try:
            # Intel CPU little-endian format only
            rec_len, rec_typ, rec_sub = struct.unpack('<HBB', data[:4])

            # Validate record length
            if rec_len > STDFConstants.MAX_RECORD_LENGTH:
                raise CorruptedSTDFFileError(
                    f"Invalid record length: {rec_len}"
                )

            return rec_len, rec_typ, rec_sub

        except struct.error as e:
            raise CorruptedSTDFFileError(f"Failed to parse record header: {e}")

    def is_valid_for_package_test(self) -> bool:
        """
        Check if this record is valid for package test processing.

        Returns:
            bool: True if record is valid for package test
        """
        return is_package_test_record(self.record_type, self.record_subtype)

    def __str__(self) -> str:
        """String representation of the record."""
        record_name = getattr(self, 'RECORD_NAME', 'Unknown')
        return (f"{record_name}({self.record_type}:{self.record_subtype}) "
                f"at position {self.file_position}")

    def __repr__(self) -> str:
        """Detailed string representation of the record."""
        return (f"{self.__class__.__name__}("
                f"type={self.record_type}, "
                f"subtype={self.record_subtype}, "
                f"length={self.record_length}, "
                f"position={self.file_position})")


class RecordFactory:
    """Factory class for creating STDF record instances."""

    # Registry of record classes by (type, subtype)
    _record_classes: Dict[Tuple[int, int], type] = {}

    @classmethod
    def register_record_class(cls, record_type: int, record_subtype: int,
                            record_class: type) -> None:
        """
        Register a record class for a specific type/subtype combination.

        Args:
            record_type: STDF record type
            record_subtype: STDF record subtype
            record_class: Record class to handle this type/subtype
        """
        cls._record_classes[(record_type, record_subtype)] = record_class

    @classmethod
    def create_record(cls, record_type: int, record_subtype: int,
                     data: bytes, position: int) -> STDFV4Record:
        """
        Create appropriate record instance based on type/subtype using T054 two-tier system.

        T054 Two-Tier System:
        - Priority records: Enhanced field access with specialized parsing
        - Non-priority records: Basic parsing without enhanced field access
        - Wafer test records: Rejected (UnsupportedRecordTypeError)
        - Unknown records: Generic parsing

        Args:
            record_type: STDF record type
            record_subtype: STDF record subtype
            data: Binary record data
            position: File position

        Returns:
            STDFV4Record: Appropriate record instance based on tier classification

        Raises:
            UnsupportedRecordTypeError: If record type is wafer test specific
            RecordParsingError: If parsing fails
        """
        # Get record tier classification
        tier = get_record_tier(record_type, record_subtype)

        # Handle wafer test records (explicitly rejected)
        if tier == 'wafer_test':
            raise UnsupportedRecordTypeError(
                record_type, record_subtype,
                "Wafer test records are not supported"
            )

        # Handle priority records (enhanced field access)
        elif tier == 'priority':
            # Look up specific priority record class
            record_class = cls._record_classes.get((record_type, record_subtype))
            if record_class:
                try:
                    return record_class.parse(data, position)
                except Exception as e:
                    raise RecordParsingError(
                        record_type, record_subtype, str(e), position=position
                    )
            else:
                # Priority record type not registered - this shouldn't happen
                raise RecordParsingError(
                    record_type, record_subtype,
                    f"Priority record type {record_type}:{record_subtype} not registered",
                    position=position
                )

        # Handle non-priority records (basic parsing only)
        elif tier == 'non_priority':
            try:
                return NonPriorityRecord.parse(data, position, record_type, record_subtype)
            except Exception as e:
                raise RecordParsingError(
                    record_type, record_subtype, str(e), position=position
                )

        # Handle unknown records (not in any defined category)
        else:
            # Create generic record for completely unknown types
            return UnknownRecord.parse(data, position, record_type, record_subtype)

    @classmethod
    def get_supported_record_types(cls) -> Dict[Tuple[int, int], str]:
        """
        Get list of supported record types.

        Returns:
            Dict[Tuple[int, int], str]: Mapping of (type, subtype) to class name
        """
        return {
            key: record_class.__name__
            for key, record_class in cls._record_classes.items()
        }


@dataclass
class UnknownRecord(STDFV4Record):
    """Record class for unknown but valid record types."""

    raw_data: bytes

    RECORD_NAME: ClassVar[str] = "Unknown"

    @classmethod
    def parse(cls, data: bytes, position: int,
              record_type: int = 0, record_subtype: int = 0) -> 'UnknownRecord':
        """
        Parse unknown record type (Intel CPU little-endian only).

        Args:
            data: Binary record data
            position: File position
            record_type: Record type from header
            record_subtype: Record subtype from header

        Returns:
            UnknownRecord: Generic record instance
        """
        return cls(
            record_type=record_type,
            record_subtype=record_subtype,
            record_length=len(data),
            file_position=position,
            raw_data=data
        )

    @property
    def record_name(self) -> str:
        """Return record name."""
        return "Unknown"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding raw binary data."""
        result = super().to_dict()
        result['raw_data_length'] = len(self.raw_data)
        # Don't include raw_data in dict to avoid binary serialization issues
        if 'raw_data' in result:
            del result['raw_data']
        return result


@dataclass
class NonPriorityRecord(STDFV4Record):
    """
    T054: Record class for non-priority STDF records (valid but no enhanced field access).

    Non-priority records are valid package test records that don't have enhanced
    field access capabilities. They provide basic parsing and identification but
    don't include the advanced field extraction features of priority records.
    """

    raw_data: bytes = b''
    parsed_fields: Optional[Dict[str, Any]] = None

    # Class constants
    RECORD_TYPE: ClassVar[int] = 0
    RECORD_SUBTYPE: ClassVar[int] = 0
    RECORD_NAME: ClassVar[str] = "NonPriority"

    @classmethod
    def parse(cls, data: bytes, position: int,
              record_type: int = 0, record_subtype: int = 0) -> 'NonPriorityRecord':
        """
        Parse non-priority record type (Intel CPU little-endian only).

        Args:
            data: Binary record data
            position: File position
            record_type: Record type from header
            record_subtype: Record subtype from header

        Returns:
            NonPriorityRecord: Non-priority record instance
        """
        # Perform basic validation
        tier = get_record_tier(record_type, record_subtype)
        if tier != 'non_priority':
            raise RecordParsingError(
                record_type, record_subtype,
                f"Record type {record_type}:{record_subtype} is not a non-priority record (tier: {tier})",
                position=position
            )

        # Create basic parsed fields dictionary (minimal parsing)
        parsed_fields = {
            'record_tier': 'non_priority',
            'data_length': len(data),
            'parsing_timestamp': int(time.time()) if 'time' in globals() else None
        }

        return cls(
            record_type=record_type,
            record_subtype=record_subtype,
            record_length=len(data),
            file_position=position,
            raw_data=data,
            parsed_fields=parsed_fields
        )

    @property
    def record_name(self) -> str:
        """Return record name with type/subtype info."""
        return f"NonPriority({self.record_type}:{self.record_subtype})"

    @property
    def is_priority_record(self) -> bool:
        """Non-priority records are not priority records."""
        return False

    @property
    def is_non_priority_record(self) -> bool:
        """Identify this as a non-priority record."""
        return True

    @property
    def record_tier(self) -> str:
        """Return the record tier classification."""
        return 'non_priority'

    def get_basic_info(self) -> Dict[str, Any]:
        """
        Get basic information about this non-priority record.

        Returns:
            Dict[str, Any]: Basic record information without enhanced field access
        """
        return {
            'record_name': self.record_name,
            'record_type': self.record_type,
            'record_subtype': self.record_subtype,
            'record_tier': self.record_tier,
            'file_position': self.file_position,
            'data_length': self.record_length,
            'has_enhanced_access': False,
            'parsed_fields': self.parsed_fields.copy() if self.parsed_fields else {}
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding raw binary data."""
        result = super().to_dict()

        # Add non-priority specific fields
        result.update({
            'record_tier': self.record_tier,
            'is_priority_record': self.is_priority_record,
            'is_non_priority_record': self.is_non_priority_record,
            'raw_data_length': len(self.raw_data),
            'has_enhanced_access': False
        })

        # Include parsed fields if available
        if self.parsed_fields:
            result['parsed_fields'] = self.parsed_fields

        # Don't include raw_data in dict to avoid binary serialization issues
        if 'raw_data' in result:
            del result['raw_data']

        return result

    def __str__(self) -> str:
        """String representation of the non-priority record."""
        return (f"NonPriorityRecord({self.record_type}:{self.record_subtype}) "
                f"at position {self.file_position}")

    def __repr__(self) -> str:
        """Detailed string representation of the non-priority record."""
        return (f"{self.__class__.__name__}("
                f"type={self.record_type}, "
                f"subtype={self.record_subtype}, "
                f"length={self.record_length}, "
                f"position={self.file_position}, "
                f"tier='non_priority')")


def validate_record_sequence(records: list) -> bool:
    """
    Validate sequence of records for package test context.

    This is a basic validation - more sophisticated sequence validation
    will be implemented in the parser module.

    Args:
        records: List of STDF records

    Returns:
        bool: True if sequence appears valid
    """
    if not records:
        return True

    # Basic checks:
    # 1. First record should be FAR
    # 2. Should have MIR record
    # 3. Should not have wafer test records

    first_record = records[0]
    if (first_record.record_type != RecordType.FAR or
        first_record.record_subtype != RecordSubtype.FAR_SUBTYPE):
        return False

    # Check for presence of MIR record
    has_mir = any(
        r.record_type == RecordType.MIR and
        r.record_subtype == RecordSubtype.MIR_SUBTYPE
        for r in records
    )

    if not has_mir:
        return False

    # All basic checks passed
    return True