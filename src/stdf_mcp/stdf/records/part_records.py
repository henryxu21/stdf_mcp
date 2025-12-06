"""
STDF-V4 part information record implementations.

This module implements the part-level STDF-V4 record types including:
- PIR (Part Information Record)
- PRR (Part Results Record)

These records contain information about individual parts/devices under test.
"""

import struct
from dataclasses import dataclass
from typing import Optional, ClassVar, Dict, Any
from datetime import datetime

from ..types import (
    TestFlag, parse_variable_length_string, parse_variable_length_binary,
    STDF_DATA_TYPES, STDFConstants
)
from ..exceptions import RecordParsingError
from .base import STDFV4Record


@dataclass
class PIRRecord(STDFV4Record):
    """
    Part Information Record (PIR) - Type 5, Subtype 10.

    Marks the beginning of test data for a part/device.
    """

    head_num: int
    site_num: int

    RECORD_TYPE: ClassVar[int] = 5
    RECORD_SUBTYPE: ClassVar[int] = 10
    RECORD_NAME: ClassVar[str] = "PIR"

    @classmethod
    def parse(cls, data: bytes, position: int) -> 'PIRRecord':
        """
        Parse PIR record from binary data (Intel CPU little-endian only).

        PIR structure: HEAD_NUM(1) + SITE_NUM(1)
        """
        if len(data) < 2:
            raise RecordParsingError(
                cls.RECORD_TYPE, cls.RECORD_SUBTYPE,
                f"Insufficient data for PIR record: {len(data)} bytes",
                position=position
            )

        try:
            # Intel CPU little-endian format only
            head_num, site_num = struct.unpack('<BB', data[:2])

            return cls(
                record_type=cls.RECORD_TYPE,
                record_subtype=cls.RECORD_SUBTYPE,
                record_length=len(data),
                file_position=position,
                head_num=head_num,
                site_num=site_num
            )

        except struct.error as e:
            raise RecordParsingError(
                cls.RECORD_TYPE, cls.RECORD_SUBTYPE,
                f"Failed to parse PIR record: {e}",
                position=position
            )

    def get_site_identifier(self) -> str:
        """Get human-readable site identifier."""
        return f"Head {self.head_num}, Site {self.site_num}"

    @property
    def is_priority_record(self) -> bool:
        """PIR is a priority record requiring complete field extraction."""
        return True

    @property
    def record_name(self) -> str:
        """Return record name."""
        return "PIR"

    def get_enhanced_field_dict(self) -> Dict[str, Any]:
        """Get all fields as dictionary."""
        return {
            'record_type': self.record_type,
            'record_subtype': self.record_subtype,
            'head_num': self.head_num,
            'site_num': self.site_num
        }


@dataclass
class PRRRecord(STDFV4Record):
    """
    Part Results Record (PRR) - Type 5, Subtype 20.

    Contains final test results and disposition for a part/device.
    Enhanced for complete field extraction according to STDF-V4 specification.
    """

    # Basic required fields
    head_num: int
    site_num: int
    part_flg: int
    num_test: int
    hard_bin: int
    soft_bin: int = 0

    # Enhanced coordinate and timing fields
    x_coord: int = 0        # X coordinate (I2)
    y_coord: int = 0        # Y coordinate (I2)
    test_t: int = 0         # Test time in milliseconds (U4)

    # Enhanced string and binary fields
    part_id: str = ""       # Part identifier (Cn)
    part_txt: str = ""      # Part description (Cn)
    part_fix: bytes = b""   # Part repair information (Bn)

    RECORD_TYPE: ClassVar[int] = 5
    RECORD_SUBTYPE: ClassVar[int] = 20
    RECORD_NAME: ClassVar[str] = "PRR"

    @classmethod
    def parse(cls, data: bytes, position: int) -> 'PRRRecord':
        """
        Parse PRR record from binary data with complete field extraction.

        PRR structure: HEAD_NUM(1) + SITE_NUM(1) + PART_FLG(1) + NUM_TEST(2) +
        HARD_BIN(2) + SOFT_BIN(2) + X_COORD(2) + Y_COORD(2) + TEST_T(4) +
        PART_ID(Cn) + PART_TXT(Cn) + PART_FIX(Bn)
        """
        if len(data) < 9:  # Minimum for required fields
            raise RecordParsingError(
                cls.RECORD_TYPE, cls.RECORD_SUBTYPE,
                f"Insufficient data for PRR record: {len(data)} bytes",
                position=position
            )

        try:
            offset = 0

            # Parse required fields (Intel CPU little-endian format)
            head_num, site_num, part_flg, num_test = struct.unpack(
                '<BBBH', data[offset:offset+5]
            )
            offset += 5

            # Parse HARD_BIN
            hard_bin = struct.unpack('<H', data[offset:offset+2])[0]
            offset += 2

            # Parse enhanced fields with defaults
            soft_bin = 0
            x_coord = 0
            y_coord = 0
            test_t = 0
            part_id = ""
            part_txt = ""
            part_fix = b""

            # Parse SOFT_BIN
            if offset + 2 <= len(data):
                soft_bin = struct.unpack('<H', data[offset:offset+2])[0]
                offset += 2

            # Parse coordinates (signed integers)
            if offset + 2 <= len(data):
                x_coord = struct.unpack('<h', data[offset:offset+2])[0]
                offset += 2

            if offset + 2 <= len(data):
                y_coord = struct.unpack('<h', data[offset:offset+2])[0]
                offset += 2

            # Parse test time
            if offset + 4 <= len(data):
                test_t = struct.unpack('<I', data[offset:offset+4])[0]
                offset += 4

            # Parse variable-length string fields
            if offset < len(data):
                part_id, offset = parse_variable_length_string(data, offset)
                part_id = part_id or ""

            if offset < len(data):
                part_txt, offset = parse_variable_length_string(data, offset)
                part_txt = part_txt or ""

            # Parse remaining bytes as binary repair data (not variable-length format)
            if offset < len(data):
                part_fix = data[offset:]
            else:
                part_fix = b""

            return cls(
                record_type=cls.RECORD_TYPE,
                record_subtype=cls.RECORD_SUBTYPE,
                record_length=len(data),
                file_position=position,
                head_num=head_num,
                site_num=site_num,
                part_flg=part_flg,
                num_test=num_test,
                hard_bin=hard_bin,
                soft_bin=soft_bin,
                x_coord=x_coord,
                y_coord=y_coord,
                test_t=test_t,
                part_id=part_id,
                part_txt=part_txt,
                part_fix=part_fix
            )

        except (struct.error, ValueError) as e:
            raise RecordParsingError(
                cls.RECORD_TYPE, cls.RECORD_SUBTYPE,
                f"Failed to parse PRR record: {e}",
                position=position
            )

    def is_passing(self) -> bool:
        """Determine if this part passed testing."""
        # Check part flag - bit 0 indicates pass/fail
        return (self.part_flg & 0x01) == 0

    def is_failing(self) -> bool:
        """Determine if this part failed testing."""
        return not self.is_passing()

    def get_test_time_seconds(self) -> Optional[float]:
        """Get test time in seconds."""
        if self.test_t is not None:
            return self.test_t / 1000.0  # Convert milliseconds to seconds
        return None

    def get_site_identifier(self) -> str:
        """Get human-readable site identifier."""
        return f"Head {self.head_num}, Site {self.site_num}"

    def get_coordinates(self) -> Optional[tuple]:
        """Get part coordinates as (x, y) tuple."""
        if self.x_coord is not None and self.y_coord is not None:
            return (self.x_coord, self.y_coord)
        return None

    def get_bin_summary(self) -> Dict[str, Any]:
        """Get bin assignment summary."""
        return {
            'hard_bin': self.hard_bin,
            'soft_bin': self.soft_bin,
            'passing': self.is_passing(),
            'bin_description': self._get_bin_description()
        }

    def _get_bin_description(self) -> str:
        """Get description of bin assignment."""
        if self.is_passing():
            return f"Pass - Hard Bin {self.hard_bin}"
        else:
            return f"Fail - Hard Bin {self.hard_bin}"

    def get_part_flags_description(self) -> Dict[str, bool]:
        """Get detailed part flag breakdown."""
        return {
            'pass_fail': (self.part_flg & 0x01) == 0,  # 0=pass, 1=fail
            'part_tested': (self.part_flg & 0x02) == 0,  # 0=tested, 1=not tested
            'part_abnormal': (self.part_flg & 0x04) != 0,  # 1=abnormal test
            'part_failed_test': (self.part_flg & 0x08) != 0,  # 1=failed during test
            'part_no_contact': (self.part_flg & 0x10) != 0  # 1=no electrical contact
        }

    @property
    def is_priority_record(self) -> bool:
        """PRR is a priority record requiring complete field extraction."""
        return True

    @property
    def is_enhanced_record(self) -> bool:
        """PRR is an enhanced record with complete field access."""
        return True

    @property
    def record_name(self) -> str:
        """Return record name."""
        return "PRR"

    def get_enhanced_field_dict(self) -> Dict[str, Any]:
        """Get all enhanced fields as dictionary."""
        return {
            'head_num': self.head_num,
            'site_num': self.site_num,
            'part_flg': self.part_flg,
            'num_test': self.num_test,
            'hard_bin': self.hard_bin,
            'soft_bin': self.soft_bin,
            'x_coord': self.x_coord,
            'y_coord': self.y_coord,
            'test_t': self.test_t,
            'part_id': self.part_id,
            'part_txt': self.part_txt,
            'part_fix': self.part_fix
        }

    def validate_coordinates(self) -> bool:
        """Validate coordinate fields."""
        return isinstance(self.x_coord, int) and isinstance(self.y_coord, int)

    def get_coordinate_tuple(self) -> tuple:
        """Get coordinates as (x, y) tuple."""
        return (self.x_coord, self.y_coord)

    def is_passing_part(self) -> bool:
        """Determine if this is a passing part (alias for is_passing)."""
        return self.is_passing()

    def get_test_time_seconds(self) -> float:
        """Get test time in seconds."""
        return self.test_t / 1000.0

    def get_test_time_minutes(self) -> float:
        """Get test time in minutes."""
        return self.test_t / 60000.0


# Register record classes with factory
def register_part_records():
    """Register part record classes with the record factory."""
    from .base import RecordFactory

    RecordFactory.register_record_class(
        PIRRecord.RECORD_TYPE, PIRRecord.RECORD_SUBTYPE, PIRRecord
    )
    RecordFactory.register_record_class(
        PRRRecord.RECORD_TYPE, PRRRecord.RECORD_SUBTYPE, PRRRecord
    )


# Auto-register when module is imported
register_part_records()