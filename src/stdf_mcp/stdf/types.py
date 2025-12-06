"""
STDF-V4 data type definitions and utilities.

This module defines all STDF-V4 data types, constants, and utility functions
for parsing and handling STDF binary data structures according to the
STDF-V4 specification.
"""

import struct
from typing import Any, Dict, List, Optional, Union, Tuple
from enum import Enum, IntEnum
from dataclasses import dataclass
from datetime import datetime


class CPUType(IntEnum):
    """CPU type constants from STDF-V4 specification."""
    SUN_SPARC = 0    # SUN SPARC (big-endian)
    VAX = 1          # VAX (little-endian)
    INTEL_X86 = 2    # Intel x86 (little-endian)


class STDFVersion(IntEnum):
    """STDF version constants."""
    V3 = 3
    V4 = 4


class TestFlag(IntEnum):
    """Test flag values for test result interpretation."""
    PASS = 0
    FAIL = 1
    ALARM = 2
    INVALID = 4
    TIMEOUT = 8
    NO_EXEC = 16


class RecordType(IntEnum):
    """STDF-V4 record type constants."""
    # File Information Records
    FAR = 0   # File Attribute Record
    ATR = 1   # Audit Trail Record

    # Master Information Records
    MIR = 1   # Master Information Record
    MRR = 1   # Master Results Record
    PCR = 1   # Part Count Record
    HBR = 1   # Hardware Bin Record
    SBR = 1   # Software Bin Record
    PMR = 1   # Pin Map Record
    PGR = 1   # Pin Group Record
    PLR = 1   # Pin List Record
    RDR = 1   # Retest Data Record
    SDR = 1   # Site Description Record

    # Wafer Information Records (REJECTED - Package test only)
    WIR = 2   # Wafer Information Record
    WRR = 2   # Wafer Results Record
    WCR = 2   # Wafer Configuration Record

    # Part Information Records
    PIR = 5   # Part Information Record
    PRR = 5   # Part Results Record

    # Test Records
    TSR = 10  # Test Synopsis Record
    PTR = 15  # Parametric Test Record
    MPR = 15  # Multiple-Result Parametric Record
    FTR = 15  # Functional Test Record
    BPS = 20  # Begin Program Section Record
    EPS = 20  # End Program Section Record

    # Generic Data Records
    GDR = 50  # Generic Data Record
    DTR = 50  # Datalog Text Record


class RecordSubtype(IntEnum):
    """STDF-V4 record subtype constants."""
    # File Records
    FAR_SUBTYPE = 10
    ATR_SUBTYPE = 10

    # Master Records
    MIR_SUBTYPE = 10
    MRR_SUBTYPE = 20
    PCR_SUBTYPE = 30
    HBR_SUBTYPE = 40
    SBR_SUBTYPE = 50
    PMR_SUBTYPE = 60
    PGR_SUBTYPE = 62
    PLR_SUBTYPE = 63
    RDR_SUBTYPE = 70
    SDR_SUBTYPE = 80

    # Wafer Records (REJECTED)
    WIR_SUBTYPE = 10
    WRR_SUBTYPE = 20
    WCR_SUBTYPE = 30

    # Part Records
    PIR_SUBTYPE = 10
    PRR_SUBTYPE = 20

    # Test Records
    TSR_SUBTYPE = 30
    PTR_SUBTYPE = 10
    MPR_SUBTYPE = 15
    FTR_SUBTYPE = 20

    # Program Section Records
    BPS_SUBTYPE = 10
    EPS_SUBTYPE = 20

    # Generic Records
    GDR_SUBTYPE = 10
    DTR_SUBTYPE = 30


# STDF-V4 package test record types (supported records only)
PACKAGE_TEST_RECORDS = {
    (RecordType.FAR, RecordSubtype.FAR_SUBTYPE),  # File Attribute
    (RecordType.ATR, RecordSubtype.ATR_SUBTYPE),  # Audit Trail
    (RecordType.MIR, RecordSubtype.MIR_SUBTYPE),  # Master Information
    (RecordType.MRR, RecordSubtype.MRR_SUBTYPE),  # Master Results
    (RecordType.PCR, RecordSubtype.PCR_SUBTYPE),  # Part Count
    (RecordType.HBR, RecordSubtype.HBR_SUBTYPE),  # Hardware Bin
    (RecordType.SBR, RecordSubtype.SBR_SUBTYPE),  # Software Bin
    (RecordType.PMR, RecordSubtype.PMR_SUBTYPE),  # Pin Map
    (RecordType.PGR, RecordSubtype.PGR_SUBTYPE),  # Pin Group
    (RecordType.PLR, RecordSubtype.PLR_SUBTYPE),  # Pin List
    (RecordType.RDR, RecordSubtype.RDR_SUBTYPE),  # Retest Data
    (RecordType.SDR, RecordSubtype.SDR_SUBTYPE),  # Site Description
    (RecordType.PIR, RecordSubtype.PIR_SUBTYPE),  # Part Information
    (RecordType.PRR, RecordSubtype.PRR_SUBTYPE),  # Part Results
    (RecordType.TSR, RecordSubtype.TSR_SUBTYPE),  # Test Synopsis
    (RecordType.PTR, RecordSubtype.PTR_SUBTYPE),  # Parametric Test
    (RecordType.MPR, RecordSubtype.MPR_SUBTYPE),  # Multiple-Result Parametric
    (RecordType.FTR, RecordSubtype.FTR_SUBTYPE),  # Functional Test
    (RecordType.BPS, RecordSubtype.BPS_SUBTYPE),  # Begin Program Section
    (RecordType.EPS, RecordSubtype.EPS_SUBTYPE),  # End Program Section
    (RecordType.GDR, RecordSubtype.GDR_SUBTYPE),  # Generic Data
    (RecordType.DTR, RecordSubtype.DTR_SUBTYPE),  # Datalog Text
}

# Wafer test record types (explicitly rejected)
WAFER_TEST_RECORDS = {
    (RecordType.WIR, RecordSubtype.WIR_SUBTYPE),  # Wafer Information
    (RecordType.WRR, RecordSubtype.WRR_SUBTYPE),  # Wafer Results
    (RecordType.WCR, RecordSubtype.WCR_SUBTYPE),  # Wafer Configuration
}

# T054: Priority record types (with enhanced field access)
PRIORITY_RECORDS = {
    # File records
    (RecordType.FAR, RecordSubtype.FAR_SUBTYPE),  # File Attribute Record
    (RecordType.MIR, RecordSubtype.MIR_SUBTYPE),  # Master Information Record
    (RecordType.MRR, RecordSubtype.MRR_SUBTYPE),  # Master Results Record

    # Part records
    (RecordType.PIR, RecordSubtype.PIR_SUBTYPE),  # Part Information Record
    (RecordType.PRR, RecordSubtype.PRR_SUBTYPE),  # Part Results Record

    # Test records
    (RecordType.PTR, RecordSubtype.PTR_SUBTYPE),  # Parametric Test Record
    (RecordType.FTR, RecordSubtype.FTR_SUBTYPE),  # Functional Test Record

    # Summary records
    (RecordType.PCR, RecordSubtype.PCR_SUBTYPE),  # Part Count Record
    (RecordType.HBR, RecordSubtype.HBR_SUBTYPE),  # Hardware Bin Record
    (RecordType.SBR, RecordSubtype.SBR_SUBTYPE),  # Software Bin Record
    (RecordType.TSR, RecordSubtype.TSR_SUBTYPE),  # Test Synopsis Record

    # Specialized records
    (RecordType.BPS, RecordSubtype.BPS_SUBTYPE),  # Begin Program Section Record
    (RecordType.DTR, RecordSubtype.DTR_SUBTYPE),  # Datalog Text Record (50, 30)
    (RecordType.GDR, RecordSubtype.GDR_SUBTYPE),  # Generic Data Record
    (RecordType.RDR, RecordSubtype.RDR_SUBTYPE),  # Retest Data Record
    (RecordType.SDR, RecordSubtype.SDR_SUBTYPE),  # Site Description Record
}

# T054: Non-priority record types (valid package records without enhanced field access)
NON_PRIORITY_RECORDS = {
    # Records that are valid for package test but not priority
    # Note: ATR conflicts with MIR (both 1,10), so excluding ATR for now
    (RecordType.PMR, RecordSubtype.PMR_SUBTYPE),  # Pin Map Record (1, 60)
    (RecordType.PGR, RecordSubtype.PGR_SUBTYPE),  # Pin Group Record (1, 62)
    (RecordType.PLR, RecordSubtype.PLR_SUBTYPE),  # Pin List Record (1, 63)
    (RecordType.MPR, RecordSubtype.MPR_SUBTYPE),  # Multiple-Result Parametric Record (15, 15)
    (RecordType.EPS, RecordSubtype.EPS_SUBTYPE),  # End Program Section Record (20, 20)
    # ATR (1, 10) conflicts with MIR and will be treated as unknown for now
}


@dataclass
class STDFDataType:
    """Base class for STDF data type definitions."""
    name: str
    size: Optional[int]  # None for variable-length types
    struct_format: str
    description: str


# STDF-V4 data type definitions
STDF_DATA_TYPES = {
    'U1': STDFDataType('U1', 1, 'B', 'Unsigned 1-byte integer'),
    'U2': STDFDataType('U2', 2, 'H', 'Unsigned 2-byte integer'),
    'U4': STDFDataType('U4', 4, 'I', 'Unsigned 4-byte integer'),
    'U8': STDFDataType('U8', 8, 'Q', 'Unsigned 8-byte integer'),
    'I1': STDFDataType('I1', 1, 'b', 'Signed 1-byte integer'),
    'I2': STDFDataType('I2', 2, 'h', 'Signed 2-byte integer'),
    'I4': STDFDataType('I4', 4, 'i', 'Signed 4-byte integer'),
    'I8': STDFDataType('I8', 8, 'q', 'Signed 8-byte integer'),
    'R4': STDFDataType('R4', 4, 'f', '4-byte IEEE 754 float'),
    'R8': STDFDataType('R8', 8, 'd', '8-byte IEEE 754 double'),
    'Cn': STDFDataType('Cn', None, 's', 'Variable-length character string'),
    'Bn': STDFDataType('Bn', None, 's', 'Variable-length binary data'),
    'Dn': STDFDataType('Dn', None, 's', 'Variable-length bit field'),
    'N1': STDFDataType('N1', 1, 'B', '1-byte nibble'),
}


def get_endian_format(cpu_type: CPUType) -> str:
    """
    Get struct format endianness character based on CPU type.

    Args:
        cpu_type: CPU type from FAR record

    Returns:
        str: Endianness format character ('<' or '>')

    Raises:
        ValueError: If CPU type is not supported
    """
    if cpu_type == CPUType.LITTLE_ENDIAN:
        return '<'
    elif cpu_type in (CPUType.BIG_ENDIAN, CPUType.SUN_SPARC):
        return '>'
    else:
        raise ValueError(f"Unsupported CPU type: {cpu_type}")


def create_struct_format(endian: str, data_types: List[str]) -> str:
    """
    Create struct format string for STDF data types.

    Args:
        endian: Endianness character ('<' or '>')
        data_types: List of STDF data type names

    Returns:
        str: Complete struct format string

    Raises:
        ValueError: If data type is not supported
    """
    format_chars = []
    for data_type in data_types:
        if data_type not in STDF_DATA_TYPES:
            raise ValueError(f"Unsupported STDF data type: {data_type}")
        format_chars.append(STDF_DATA_TYPES[data_type].struct_format)

    return endian + ''.join(format_chars)


def parse_variable_length_string(data: bytes, offset: int) -> Tuple[str, int]:
    """
    Parse variable-length string (Cn type) from binary data.

    Args:
        data: Binary data containing the string
        offset: Starting offset in data

    Returns:
        Tuple[str, int]: Parsed string and new offset

    Raises:
        ValueError: If data is insufficient
    """
    if offset >= len(data):
        return "", offset

    # First byte is length
    if offset + 1 > len(data):
        raise ValueError("Insufficient data for string length")

    length = data[offset]
    offset += 1

    if offset + length > len(data):
        raise ValueError(f"Insufficient data for string of length {length}")

    if length == 0:
        return "", offset

    string_data = data[offset:offset + length]
    offset += length

    # Decode string, handling potential encoding issues
    try:
        return string_data.decode('ascii', errors='replace'), offset
    except UnicodeDecodeError:
        return string_data.decode('latin1', errors='replace'), offset


def parse_variable_length_binary(data: bytes, offset: int) -> Tuple[bytes, int]:
    """
    Parse variable-length binary data (Bn type) from binary data.

    Args:
        data: Binary data containing the binary field
        offset: Starting offset in data

    Returns:
        Tuple[bytes, int]: Parsed binary data and new offset

    Raises:
        ValueError: If data is insufficient
    """
    if offset >= len(data):
        return b"", offset

    # First byte is length
    if offset + 1 > len(data):
        raise ValueError("Insufficient data for binary length")

    length = data[offset]
    offset += 1

    if offset + length > len(data):
        raise ValueError(f"Insufficient data for binary of length {length}")

    if length == 0:
        return b"", offset

    binary_data = data[offset:offset + length]
    offset += length

    return binary_data, offset


def format_stdf_timestamp(timestamp: int) -> datetime:
    """
    Convert STDF timestamp to datetime object.

    STDF timestamps are seconds since 00:00:00 Jan 1, 1970 (Unix epoch)

    Args:
        timestamp: STDF timestamp value

    Returns:
        datetime: Converted datetime object
    """
    if timestamp == 0:
        # Return epoch for 0 timestamp
        return datetime.fromtimestamp(0)

    return datetime.fromtimestamp(timestamp)


def is_package_test_record(record_type: int, record_subtype: int) -> bool:
    """
    Check if record type/subtype is valid for package test.

    Args:
        record_type: STDF record type
        record_subtype: STDF record subtype

    Returns:
        bool: True if record is valid for package test
    """
    return (record_type, record_subtype) in PACKAGE_TEST_RECORDS


def is_wafer_test_record(record_type: int, record_subtype: int) -> bool:
    """
    Check if record type/subtype is wafer test specific.

    Args:
        record_type: STDF record type
        record_subtype: STDF record subtype

    Returns:
        bool: True if record is wafer test specific
    """
    return (record_type, record_subtype) in WAFER_TEST_RECORDS


# T054: Two-tier record classification functions

def is_priority_record(record_type: int, record_subtype: int) -> bool:
    """
    Check if record type/subtype is a priority record with enhanced field access.

    Args:
        record_type: STDF record type
        record_subtype: STDF record subtype

    Returns:
        bool: True if record is a priority record (has enhanced field access)
    """
    return (record_type, record_subtype) in PRIORITY_RECORDS


def is_non_priority_record(record_type: int, record_subtype: int) -> bool:
    """
    Check if record type/subtype is a non-priority record (valid but no enhanced access).

    Args:
        record_type: STDF record type
        record_subtype: STDF record subtype

    Returns:
        bool: True if record is non-priority (valid for package test but no enhanced access)
    """
    return (record_type, record_subtype) in NON_PRIORITY_RECORDS


def get_record_tier(record_type: int, record_subtype: int) -> str:
    """
    Get the tier classification for a record type/subtype.

    Args:
        record_type: STDF record type
        record_subtype: STDF record subtype

    Returns:
        str: Record tier - 'priority', 'non_priority', 'wafer_test', or 'unknown'
    """
    if is_priority_record(record_type, record_subtype):
        return 'priority'
    elif is_non_priority_record(record_type, record_subtype):
        return 'non_priority'
    elif is_wafer_test_record(record_type, record_subtype):
        return 'wafer_test'
    else:
        return 'unknown'


def get_priority_record_types() -> set:
    """
    Get the set of all priority record types with enhanced field access.

    Returns:
        set: Set of (record_type, record_subtype) tuples for priority records
    """
    return PRIORITY_RECORDS.copy()


def get_non_priority_record_types() -> set:
    """
    Get the set of all non-priority record types (valid but no enhanced access).

    Returns:
        set: Set of (record_type, record_subtype) tuples for non-priority records
    """
    return NON_PRIORITY_RECORDS.copy()


def calculate_record_size(data_types: List[str]) -> Optional[int]:
    """
    Calculate total size for fixed-length record types.

    Args:
        data_types: List of STDF data type names

    Returns:
        Optional[int]: Total size in bytes, None if variable-length
    """
    total_size = 0
    for data_type in data_types:
        type_def = STDF_DATA_TYPES.get(data_type)
        if not type_def or type_def.size is None:
            return None  # Variable-length record
        total_size += type_def.size

    return total_size


def validate_record_data(data: bytes, expected_length: int) -> bool:
    """
    Validate that record data matches expected length.

    Args:
        data: Binary record data
        expected_length: Expected data length

    Returns:
        bool: True if data length matches expected
    """
    return len(data) >= expected_length


class STDFConstants:
    """Container for STDF-V4 constants and magic values."""

    # Record header size (REC_LEN + REC_TYP + REC_SUB)
    RECORD_HEADER_SIZE = 4

    # Maximum record length (64KB - 1)
    MAX_RECORD_LENGTH = 65535

    # Default test result values
    DEFAULT_MISSING_VALUE = -1
    DEFAULT_NO_LIMIT = float('inf')

    # File validation constants
    MIN_FILE_SIZE = 10  # Minimum viable STDF file size
    MAX_REASONABLE_RECORD_COUNT = 10_000_000  # Sanity check

    # Test flag combinations
    PASS_FLAGS = {TestFlag.PASS}
    FAIL_FLAGS = {TestFlag.FAIL, TestFlag.ALARM, TestFlag.TIMEOUT}
    INVALID_FLAGS = {TestFlag.INVALID, TestFlag.NO_EXEC}

    @classmethod
    def is_pass_result(cls, test_flag: int) -> bool:
        """Check if test flag indicates a passing result."""
        return test_flag in cls.PASS_FLAGS

    @classmethod
    def is_fail_result(cls, test_flag: int) -> bool:
        """Check if test flag indicates a failing result."""
        return test_flag in cls.FAIL_FLAGS

    @classmethod
    def is_invalid_result(cls, test_flag: int) -> bool:
        """Check if test flag indicates an invalid/not executed result."""
        return test_flag in cls.INVALID_FLAGS