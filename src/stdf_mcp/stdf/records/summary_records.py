"""
STDF-V4 summary record implementations.

This module implements the summary-level STDF-V4 record types including:
- PCR (Part Count Record)
- HBR (Hardware Bin Record)
- SBR (Software Bin Record)
- TSR (Test Synopsis Record)

These records provide summary statistics and bin information.
"""

import struct
from dataclasses import dataclass
from typing import Optional, ClassVar, Dict, Any, List

from ..types import (
    parse_variable_length_string, STDF_DATA_TYPES, STDFConstants
)
from ..exceptions import RecordParsingError
from .base import STDFV4Record


@dataclass
class PCRRecord(STDFV4Record):
    """
    Part Count Record (PCR) - Type 1, Subtype 30.

    Contains part count information for each test site.
    """

    head_num: int
    site_num: int
    part_cnt: int
    rtst_cnt: Optional[int] = None
    abrt_cnt: Optional[int] = None
    good_cnt: Optional[int] = None
    func_cnt: Optional[int] = None

    RECORD_TYPE: ClassVar[int] = 1
    RECORD_SUBTYPE: ClassVar[int] = 30
    RECORD_NAME: ClassVar[str] = "PCR"

    @classmethod
    def parse(cls, data: bytes, position: int) -> 'PCRRecord':
        """
        Parse PCR record from binary data (Intel CPU little-endian only).

        PCR structure: HEAD_NUM(1) + SITE_NUM(1) + PART_CNT(4) + RTST_CNT(4) +
        ABRT_CNT(4) + GOOD_CNT(4) + FUNC_CNT(4)
        """
        if len(data) < 6:  # Minimum for required fields
            raise RecordParsingError(
                cls.RECORD_TYPE, cls.RECORD_SUBTYPE,
                f"Insufficient data for PCR record: {len(data)} bytes",
                position=position
            )

        try:
            offset = 0

            # Parse required fields (Intel CPU little-endian format)
            head_num, site_num, part_cnt = struct.unpack(
                '<BBI', data[offset:offset+6]
            )
            offset += 6

            # Parse optional fields
            rtst_cnt = None
            abrt_cnt = None
            good_cnt = None
            func_cnt = None

            if offset + 4 <= len(data):
                rtst_cnt = struct.unpack('<I', data[offset:offset+4])[0]
                offset += 4

            if offset + 4 <= len(data):
                abrt_cnt = struct.unpack('<I', data[offset:offset+4])[0]
                offset += 4

            if offset + 4 <= len(data):
                good_cnt = struct.unpack('<I', data[offset:offset+4])[0]
                offset += 4

            if offset + 4 <= len(data):
                func_cnt = struct.unpack('<I', data[offset:offset+4])[0]
                offset += 4

            return cls(
                record_type=cls.RECORD_TYPE,
                record_subtype=cls.RECORD_SUBTYPE,
                record_length=len(data),
                file_position=position,
                head_num=head_num,
                site_num=site_num,
                part_cnt=part_cnt,
                rtst_cnt=rtst_cnt,
                abrt_cnt=abrt_cnt,
                good_cnt=good_cnt,
                func_cnt=func_cnt
            )

        except struct.error as e:
            raise RecordParsingError(
                cls.RECORD_TYPE, cls.RECORD_SUBTYPE,
                f"Failed to parse PCR record: {e}",
                position=position
            )

    def get_yield_percentage(self) -> Optional[float]:
        """Calculate yield percentage based on good vs total parts."""
        if self.good_cnt is not None and self.part_cnt > 0:
            return (self.good_cnt / self.part_cnt) * 100.0
        return None

    def get_retest_percentage(self) -> Optional[float]:
        """Calculate retest percentage."""
        if self.rtst_cnt is not None and self.part_cnt > 0:
            return (self.rtst_cnt / self.part_cnt) * 100.0
        return None

    def get_site_summary(self) -> Dict[str, Any]:
        """Get comprehensive site summary."""
        return {
            'site': f"Head {self.head_num}, Site {self.site_num}",
            'total_parts': self.part_cnt,
            'good_parts': self.good_cnt,
            'retested_parts': self.rtst_cnt,
            'aborted_parts': self.abrt_cnt,
            'functional_parts': self.func_cnt,
            'yield_percent': self.get_yield_percentage(),
            'retest_percent': self.get_retest_percentage()
        }

    @property
    def is_priority_record(self) -> bool:
        """PCR is a priority record requiring complete field extraction."""
        return True

    @property
    def record_name(self) -> str:
        """Return record name."""
        return "PCR"

    def get_enhanced_field_dict(self) -> Dict[str, Any]:
        """Get all fields as dictionary."""
        return {
            'record_type': self.record_type,
            'record_subtype': self.record_subtype,
            'head_num': self.head_num,
            'site_num': self.site_num,
            'part_cnt': self.part_cnt,
            'rtst_cnt': self.rtst_cnt,
            'abrt_cnt': self.abrt_cnt,
            'good_cnt': self.good_cnt,
            'func_cnt': self.func_cnt
        }


@dataclass
class HBRRecord(STDFV4Record):
    """
    Hardware Bin Record (HBR) - Type 1, Subtype 40.

    Contains hardware bin information and counts.
    """

    head_num: int
    site_num: int
    hbin_num: int
    hbin_cnt: int
    hbin_pf: Optional[str] = None
    hbin_nam: Optional[str] = None

    RECORD_TYPE: ClassVar[int] = 1
    RECORD_SUBTYPE: ClassVar[int] = 40
    RECORD_NAME: ClassVar[str] = "HBR"

    @classmethod
    def parse(cls, data: bytes, position: int) -> 'HBRRecord':
        """
        Parse HBR record from binary data (Intel CPU little-endian only).

        HBR structure: HEAD_NUM(1) + SITE_NUM(1) + HBIN_NUM(2) + HBIN_CNT(4) +
        HBIN_PF(1) + HBIN_NAM(Cn)
        """
        if len(data) < 8:  # Minimum for required fields
            raise RecordParsingError(
                cls.RECORD_TYPE, cls.RECORD_SUBTYPE,
                f"Insufficient data for HBR record: {len(data)} bytes",
                position=position
            )

        try:
            offset = 0

            # Parse required fields (Intel CPU little-endian format)
            head_num, site_num, hbin_num, hbin_cnt = struct.unpack(
                '<BBHI', data[offset:offset+8]
            )
            offset += 8

            # Parse optional fields
            hbin_pf = None
            hbin_nam = None

            if offset + 1 <= len(data):
                hbin_pf = chr(data[offset])
                offset += 1

            if offset < len(data):
                hbin_nam, offset = parse_variable_length_string(data, offset)

            return cls(
                record_type=cls.RECORD_TYPE,
                record_subtype=cls.RECORD_SUBTYPE,
                record_length=len(data),
                file_position=position,
                head_num=head_num,
                site_num=site_num,
                hbin_num=hbin_num,
                hbin_cnt=hbin_cnt,
                hbin_pf=hbin_pf,
                hbin_nam=hbin_nam
            )

        except (struct.error, ValueError) as e:
            raise RecordParsingError(
                cls.RECORD_TYPE, cls.RECORD_SUBTYPE,
                f"Failed to parse HBR record: {e}",
                position=position
            )

    def is_pass_bin(self) -> bool:
        """Determine if this is a passing hardware bin."""
        return self.hbin_pf == 'P' if self.hbin_pf else False

    def is_fail_bin(self) -> bool:
        """Determine if this is a failing hardware bin."""
        return self.hbin_pf == 'F' if self.hbin_pf else False

    def get_bin_description(self) -> str:
        """Get human-readable bin description."""
        bin_type = "Pass" if self.is_pass_bin() else "Fail"
        bin_name = self.hbin_nam or f"HBin_{self.hbin_num}"
        return f"{bin_type} - {bin_name}"

    def get_bin_summary(self) -> Dict[str, Any]:
        """Get comprehensive bin summary."""
        return {
            'bin_number': self.hbin_num,
            'bin_name': self.hbin_nam or f"HBin_{self.hbin_num}",
            'count': self.hbin_cnt,
            'pass_fail': self.hbin_pf,
            'is_passing': self.is_pass_bin(),
            'site': f"Head {self.head_num}, Site {self.site_num}",
            'description': self.get_bin_description()
        }

    @property
    def is_priority_record(self) -> bool:
        """HBR is a priority record requiring complete field extraction."""
        return True

    @property
    def record_name(self) -> str:
        """Return record name."""
        return "HBR"

    def get_enhanced_field_dict(self) -> Dict[str, Any]:
        """Get all fields as dictionary."""
        return {
            'record_type': self.record_type,
            'record_subtype': self.record_subtype,
            'head_num': self.head_num,
            'site_num': self.site_num,
            'hbin_num': self.hbin_num,
            'hbin_cnt': self.hbin_cnt,
            'hbin_pf': self.hbin_pf,
            'hbin_nam': self.hbin_nam
        }


@dataclass
class SBRRecord(STDFV4Record):
    """
    Software Bin Record (SBR) - Type 1, Subtype 50.

    Contains software bin information and counts.
    """

    head_num: int
    site_num: int
    sbin_num: int
    sbin_cnt: int
    sbin_pf: Optional[str] = None
    sbin_nam: Optional[str] = None

    RECORD_TYPE: ClassVar[int] = 1
    RECORD_SUBTYPE: ClassVar[int] = 50
    RECORD_NAME: ClassVar[str] = "SBR"

    @classmethod
    def parse(cls, data: bytes, position: int) -> 'SBRRecord':
        """
        Parse SBR record from binary data (Intel CPU little-endian only).

        SBR structure: HEAD_NUM(1) + SITE_NUM(1) + SBIN_NUM(2) + SBIN_CNT(4) +
        SBIN_PF(1) + SBIN_NAM(Cn)
        """
        if len(data) < 8:  # Minimum for required fields
            raise RecordParsingError(
                cls.RECORD_TYPE, cls.RECORD_SUBTYPE,
                f"Insufficient data for SBR record: {len(data)} bytes",
                position=position
            )

        try:
            offset = 0

            # Parse required fields (Intel CPU little-endian format)
            head_num, site_num, sbin_num, sbin_cnt = struct.unpack(
                '<BBHI', data[offset:offset+8]
            )
            offset += 8

            # Parse optional fields
            sbin_pf = None
            sbin_nam = None

            if offset + 1 <= len(data):
                sbin_pf = chr(data[offset])
                offset += 1

            if offset < len(data):
                sbin_nam, offset = parse_variable_length_string(data, offset)

            return cls(
                record_type=cls.RECORD_TYPE,
                record_subtype=cls.RECORD_SUBTYPE,
                record_length=len(data),
                file_position=position,
                head_num=head_num,
                site_num=site_num,
                sbin_num=sbin_num,
                sbin_cnt=sbin_cnt,
                sbin_pf=sbin_pf,
                sbin_nam=sbin_nam
            )

        except (struct.error, ValueError) as e:
            raise RecordParsingError(
                cls.RECORD_TYPE, cls.RECORD_SUBTYPE,
                f"Failed to parse SBR record: {e}",
                position=position
            )

    def is_pass_bin(self) -> bool:
        """Determine if this is a passing software bin."""
        return self.sbin_pf == 'P' if self.sbin_pf else False

    def is_fail_bin(self) -> bool:
        """Determine if this is a failing software bin."""
        return self.sbin_pf == 'F' if self.sbin_pf else False

    def get_bin_summary(self) -> Dict[str, Any]:
        """Get comprehensive bin summary."""
        return {
            'bin_number': self.sbin_num,
            'bin_name': self.sbin_nam or f"SBin_{self.sbin_num}",
            'count': self.sbin_cnt,
            'pass_fail': self.sbin_pf,
            'is_passing': self.is_pass_bin(),
            'site': f"Head {self.head_num}, Site {self.site_num}"
        }

    @property
    def is_priority_record(self) -> bool:
        """SBR is a priority record requiring complete field extraction."""
        return True

    @property
    def record_name(self) -> str:
        """Return record name."""
        return "SBR"

    def get_enhanced_field_dict(self) -> Dict[str, Any]:
        """Get all fields as dictionary."""
        return {
            'record_type': self.record_type,
            'record_subtype': self.record_subtype,
            'head_num': self.head_num,
            'site_num': self.site_num,
            'sbin_num': self.sbin_num,
            'sbin_cnt': self.sbin_cnt,
            'sbin_pf': self.sbin_pf,
            'sbin_nam': self.sbin_nam
        }


@dataclass
class TSRRecord(STDFV4Record):
    """
    Test Synopsis Record (TSR) - Type 10, Subtype 30.

    Contains test execution summary information.
    """

    head_num: int
    site_num: int
    test_typ: str
    test_num: int
    exec_cnt: Optional[int] = None
    fail_cnt: Optional[int] = None
    alrm_cnt: Optional[int] = None
    test_nam: Optional[str] = None
    seq_name: Optional[str] = None
    test_lbl: Optional[str] = None
    opt_flag: Optional[int] = None
    test_tim: Optional[float] = None
    test_min: Optional[float] = None
    test_max: Optional[float] = None
    tst_sums: Optional[float] = None
    tst_sqrs: Optional[float] = None

    RECORD_TYPE: ClassVar[int] = 10
    RECORD_SUBTYPE: ClassVar[int] = 30
    RECORD_NAME: ClassVar[str] = "TSR"

    @classmethod
    def parse(cls, data: bytes, position: int) -> 'TSRRecord':
        """
        Parse TSR record from binary data (Intel CPU little-endian only).

        This is a simplified implementation focusing on core fields.
        """
        if len(data) < 8:  # Minimum for required fields
            raise RecordParsingError(
                cls.RECORD_TYPE, cls.RECORD_SUBTYPE,
                f"Insufficient data for TSR record: {len(data)} bytes",
                position=position
            )

        try:
            offset = 0

            # Parse required fields (Intel CPU little-endian format)
            head_num, site_num, test_typ_byte, test_num = struct.unpack(
                '<BBBI', data[offset:offset+7]
            )
            offset += 7

            test_typ = chr(test_typ_byte)

            # Parse optional execution counts
            exec_cnt = None
            fail_cnt = None
            alrm_cnt = None

            if offset + 4 <= len(data):
                exec_cnt = struct.unpack('<I', data[offset:offset+4])[0]
                offset += 4

            if offset + 4 <= len(data):
                fail_cnt = struct.unpack('<I', data[offset:offset+4])[0]
                offset += 4

            if offset + 4 <= len(data):
                alrm_cnt = struct.unpack('<I', data[offset:offset+4])[0]
                offset += 4

            # Parse optional string fields
            test_nam = None
            seq_name = None
            test_lbl = None

            if offset < len(data):
                test_nam, offset = parse_variable_length_string(data, offset)
            if offset < len(data):
                seq_name, offset = parse_variable_length_string(data, offset)
            if offset < len(data):
                test_lbl, offset = parse_variable_length_string(data, offset)

            return cls(
                record_type=cls.RECORD_TYPE,
                record_subtype=cls.RECORD_SUBTYPE,
                record_length=len(data),
                file_position=position,
                head_num=head_num,
                site_num=site_num,
                test_typ=test_typ,
                test_num=test_num,
                exec_cnt=exec_cnt,
                fail_cnt=fail_cnt,
                alrm_cnt=alrm_cnt,
                test_nam=test_nam,
                seq_name=seq_name,
                test_lbl=test_lbl
            )

        except (struct.error, ValueError) as e:
            raise RecordParsingError(
                cls.RECORD_TYPE, cls.RECORD_SUBTYPE,
                f"Failed to parse TSR record: {e}",
                position=position
            )

    def get_pass_rate(self) -> Optional[float]:
        """Calculate pass rate percentage."""
        if self.exec_cnt and self.fail_cnt is not None:
            pass_cnt = self.exec_cnt - self.fail_cnt
            return (pass_cnt / self.exec_cnt) * 100.0
        return None

    def get_test_type_description(self) -> str:
        """Get human-readable test type description."""
        test_types = {
            'P': "Parametric",
            'F': "Functional",
            'M': "Multiple-Result Parametric"
        }
        return test_types.get(self.test_typ, f"Unknown ({self.test_typ})")

    def get_test_summary(self) -> Dict[str, Any]:
        """Get comprehensive test summary."""
        return {
            'test_number': self.test_num,
            'test_name': self.test_nam or f"Test_{self.test_num}",
            'test_type': self.get_test_type_description(),
            'site': f"Head {self.head_num}, Site {self.site_num}",
            'executions': self.exec_cnt,
            'failures': self.fail_cnt,
            'alarms': self.alrm_cnt,
            'pass_rate': self.get_pass_rate(),
            'sequence': self.seq_name,
            'label': self.test_lbl
        }

    @property
    def is_priority_record(self) -> bool:
        """TSR is a priority record requiring complete field extraction."""
        return True

    @property
    def record_name(self) -> str:
        """Return record name."""
        return "TSR"

    def get_enhanced_field_dict(self) -> Dict[str, Any]:
        """Get all fields as dictionary."""
        return {
            'record_type': self.record_type,
            'record_subtype': self.record_subtype,
            'head_num': self.head_num,
            'site_num': self.site_num,
            'test_typ': self.test_typ,
            'test_num': self.test_num,
            'exec_cnt': self.exec_cnt,
            'fail_cnt': self.fail_cnt,
            'alrm_cnt': self.alrm_cnt,
            'test_nam': self.test_nam,
            'seq_name': self.seq_name,
            'test_lbl': self.test_lbl
        }


# Register record classes with factory
def register_summary_records():
    """Register summary record classes with the record factory."""
    from .base import RecordFactory

    RecordFactory.register_record_class(
        PCRRecord.RECORD_TYPE, PCRRecord.RECORD_SUBTYPE, PCRRecord
    )
    RecordFactory.register_record_class(
        HBRRecord.RECORD_TYPE, HBRRecord.RECORD_SUBTYPE, HBRRecord
    )
    RecordFactory.register_record_class(
        SBRRecord.RECORD_TYPE, SBRRecord.RECORD_SUBTYPE, SBRRecord
    )
    RecordFactory.register_record_class(
        TSRRecord.RECORD_TYPE, TSRRecord.RECORD_SUBTYPE, TSRRecord
    )


# Auto-register when module is imported
register_summary_records()