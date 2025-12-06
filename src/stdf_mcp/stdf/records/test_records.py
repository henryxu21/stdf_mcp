"""
STDF-V4 test record implementations.

This module implements the test-level STDF-V4 record types including:
- PTR (Parametric Test Record)
- FTR (Functional Test Record)
- MPR (Multiple-Result Parametric Record)

These records contain individual test results and measurements.
"""

import struct
from dataclasses import dataclass
from typing import Optional, ClassVar, Dict, Any, List
from math import pow

from ..types import (
    TestFlag, parse_variable_length_string, parse_variable_length_binary,
    STDF_DATA_TYPES, STDFConstants
)
from ..exceptions import RecordParsingError
from .base import STDFV4Record


@dataclass
class PTRRecord(STDFV4Record):
    """
    Parametric Test Record (PTR) - Type 15, Subtype 10.

    Contains results of parametric tests (voltage, current, etc.).
    """

    test_num: int
    head_num: int
    site_num: int
    test_flg: int
    parm_flg: int
    result: Optional[float] = None
    test_txt: Optional[str] = None
    alarm_id: Optional[str] = None
    opt_flag: Optional[int] = None
    res_scal: Optional[int] = None
    llm_scal: Optional[int] = None
    hlm_scal: Optional[int] = None
    lo_limit: Optional[float] = None
    hi_limit: Optional[float] = None
    units: Optional[str] = None
    c_resfmt: Optional[str] = None
    c_llmfmt: Optional[str] = None
    c_hlmfmt: Optional[str] = None
    lo_spec: Optional[float] = None
    hi_spec: Optional[float] = None

    RECORD_TYPE: ClassVar[int] = 15
    RECORD_SUBTYPE: ClassVar[int] = 10
    RECORD_NAME: ClassVar[str] = "PTR"

    @classmethod
    def parse(cls, data: bytes, position: int) -> 'PTRRecord':
        """
        Parse PTR record from binary data (Intel CPU little-endian only).

        PTR structure: TEST_NUM(4) + HEAD_NUM(1) + SITE_NUM(1) + TEST_FLG(1) +
        PARM_FLG(1) + RESULT(4) + TEST_TXT(Cn) + ALARM_ID(Cn) + OPT_FLAG(1) +
        RES_SCAL(1) + LLM_SCAL(1) + HLM_SCAL(1) + LO_LIMIT(4) + HI_LIMIT(4) +
        UNITS(Cn) + C_RESFMT(Cn) + C_LLMFMT(Cn) + C_HLMFMT(Cn) + LO_SPEC(4) + HI_SPEC(4)
        """
        if len(data) < 8:  # Minimum for required fields
            raise RecordParsingError(
                cls.RECORD_TYPE, cls.RECORD_SUBTYPE,
                f"Insufficient data for PTR record: {len(data)} bytes",
                position=position
            )

        try:
            offset = 0

            # Parse required fields (Intel CPU little-endian format)
            test_num, head_num, site_num, test_flg, parm_flg = struct.unpack(
                '<IBBBB', data[offset:offset+8]
            )
            offset += 8

            # Parse optional RESULT field based on parm_flg
            result = None
            if offset + 4 <= len(data) and (parm_flg & 0x01) == 0:
                result = struct.unpack('<f', data[offset:offset+4])[0]
                offset += 4
            elif (parm_flg & 0x01) != 0:
                # Result is invalid/not present
                if offset + 4 <= len(data):
                    offset += 4  # Skip the result field

            # Parse optional text fields
            test_txt = None
            alarm_id = None
            if offset < len(data):
                test_txt, offset = parse_variable_length_string(data, offset)
            if offset < len(data):
                alarm_id, offset = parse_variable_length_string(data, offset)

            # Parse optional scaling and limit fields
            opt_flag = None
            res_scal = None
            llm_scal = None
            hlm_scal = None
            lo_limit = None
            hi_limit = None

            if offset + 1 <= len(data):
                opt_flag = data[offset]
                offset += 1

            if offset + 3 <= len(data):
                res_scal, llm_scal, hlm_scal = struct.unpack(
                    '<bbb', data[offset:offset+3]
                )
                offset += 3

            if offset + 8 <= len(data):
                lo_limit, hi_limit = struct.unpack(
                    '<ff', data[offset:offset+8]
                )
                offset += 8

            # Parse remaining optional string fields
            units = None
            c_resfmt = None
            c_llmfmt = None
            c_hlmfmt = None
            lo_spec = None
            hi_spec = None

            if offset < len(data):
                units, offset = parse_variable_length_string(data, offset)
            if offset < len(data):
                c_resfmt, offset = parse_variable_length_string(data, offset)
            if offset < len(data):
                c_llmfmt, offset = parse_variable_length_string(data, offset)
            if offset < len(data):
                c_hlmfmt, offset = parse_variable_length_string(data, offset)

            if offset + 8 <= len(data):
                lo_spec, hi_spec = struct.unpack(
                    '<ff', data[offset:offset+8]
                )
                offset += 8

            return cls(
                record_type=cls.RECORD_TYPE,
                record_subtype=cls.RECORD_SUBTYPE,
                record_length=len(data),
                file_position=position,
                test_num=test_num,
                head_num=head_num,
                site_num=site_num,
                test_flg=test_flg,
                parm_flg=parm_flg,
                result=result,
                test_txt=test_txt,
                alarm_id=alarm_id,
                opt_flag=opt_flag,
                res_scal=res_scal,
                llm_scal=llm_scal,
                hlm_scal=hlm_scal,
                lo_limit=lo_limit,
                hi_limit=hi_limit,
                units=units,
                c_resfmt=c_resfmt,
                c_llmfmt=c_llmfmt,
                c_hlmfmt=c_hlmfmt,
                lo_spec=lo_spec,
                hi_spec=hi_spec
            )

        except (struct.error, ValueError) as e:
            raise RecordParsingError(
                cls.RECORD_TYPE, cls.RECORD_SUBTYPE,
                f"Failed to parse PTR record: {e}",
                position=position
            )

    def is_passing(self) -> bool:
        """Determine if this test passed."""
        return STDFConstants.is_pass_result(self.test_flg)

    def is_failing(self) -> bool:
        """Determine if this test failed."""
        return STDFConstants.is_fail_result(self.test_flg)

    def is_valid_result(self) -> bool:
        """Determine if the test result is valid."""
        return self.result is not None and (self.parm_flg & 0x01) == 0

    def get_scaled_result(self) -> Optional[float]:
        """Get result with scaling factor applied."""
        if not self.is_valid_result() or self.res_scal is None:
            return self.result

        if self.res_scal == 0:
            return self.result
        elif self.res_scal > 0:
            return self.result * pow(10, self.res_scal)
        else:
            return self.result / pow(10, abs(self.res_scal))

    def get_scaled_limits(self) -> tuple:
        """Get limits with scaling factors applied."""
        lo_scaled = self.lo_limit
        hi_scaled = self.hi_limit

        if self.lo_limit is not None and self.llm_scal is not None:
            if self.llm_scal > 0:
                lo_scaled = self.lo_limit * pow(10, self.llm_scal)
            elif self.llm_scal < 0:
                lo_scaled = self.lo_limit / pow(10, abs(self.llm_scal))

        if self.hi_limit is not None and self.hlm_scal is not None:
            if self.hlm_scal > 0:
                hi_scaled = self.hi_limit * pow(10, self.hlm_scal)
            elif self.hlm_scal < 0:
                hi_scaled = self.hi_limit / pow(10, abs(self.hlm_scal))

        return lo_scaled, hi_scaled

    def is_within_limits(self) -> bool:
        """Check if result is within specified limits."""
        if not self.is_valid_result():
            return False

        scaled_result = self.get_scaled_result()
        lo_limit, hi_limit = self.get_scaled_limits()

        if lo_limit is not None and scaled_result < lo_limit:
            return False
        if hi_limit is not None and scaled_result > hi_limit:
            return False

        return True

    def get_test_summary(self) -> Dict[str, Any]:
        """Get comprehensive test summary."""
        return {
            'test_number': self.test_num,
            'test_name': self.test_txt or f"Test_{self.test_num}",
            'site': f"Head {self.head_num}, Site {self.site_num}",
            'result': self.get_scaled_result(),
            'units': self.units,
            'limits': self.get_scaled_limits(),
            'within_limits': self.is_within_limits(),
            'passing': self.is_passing(),
            'valid': self.is_valid_result()
        }

    @property
    def is_priority_record(self) -> bool:
        """PTR is a priority record requiring complete field extraction."""
        return True

    @property
    def record_name(self) -> str:
        """Return record name."""
        return "PTR"

    def get_enhanced_field_dict(self) -> Dict[str, Any]:
        """Get all fields as dictionary."""
        return {
            'record_type': self.record_type,
            'record_subtype': self.record_subtype,
            'test_num': self.test_num,
            'head_num': self.head_num,
            'site_num': self.site_num,
            'test_flg': self.test_flg,
            'parm_flg': self.parm_flg,
            'result': self.result,
            'test_txt': self.test_txt,
            'alarm_id': self.alarm_id
        }


@dataclass
class FTRRecord(STDFV4Record):
    """
    Functional Test Record (FTR) - Type 15, Subtype 20.

    Contains results of functional/digital tests with complete field extraction.
    Enhanced for complete vector/timing/binary field access according to STDF-V4 specification.
    """

    # Basic required fields
    test_num: int
    head_num: int
    site_num: int
    test_flg: int

    # Enhanced execution fields
    opt_flag: int = 0       # Optional data flag (B1)
    cyc_cnt: int = 0        # Cycle count (U4)
    rel_vadr: int = 0       # Relative vector address (U4)
    rpt_cnt: int = 0        # Repeat count (U4)
    num_fail: int = 0       # Number of failures (U4)
    xfail_ad: int = 0       # X failure address (U4)
    yfail_ad: int = 0       # Y failure address (U4)

    # Enhanced timing fields
    vect_off: int = 0       # Vector offset (U4)
    rtst_bin: List[int] = None  # Return to test bins (kxU2)

    # Enhanced string fields
    prog_txt: str = ""      # Program text (Cn)
    rslt_txt: str = ""      # Result text (Cn)

    # Enhanced binary fields
    patg_num: int = 0       # Pattern generator number (U1)
    spin_map: bytes = b""   # Spin map (Dn)

    def __post_init__(self):
        """Initialize default values for mutable fields."""
        if self.rtst_bin is None:
            self.rtst_bin = []

    RECORD_TYPE: ClassVar[int] = 15
    RECORD_SUBTYPE: ClassVar[int] = 20
    RECORD_NAME: ClassVar[str] = "FTR"

    @classmethod
    def parse(cls, data: bytes, position: int) -> 'FTRRecord':
        """
        Parse FTR record from binary data with complete field extraction.

        FTR structure: TEST_NUM(4) + HEAD_NUM(1) + SITE_NUM(1) + TEST_FLG(1) +
        OPT_FLAG(1) + CYC_CNT(4) + REL_VADR(4) + RPT_CNT(4) + NUM_FAIL(4) +
        XFAIL_AD(4) + YFAIL_AD(4) + VECT_OFF(4) + RTN_ICNT(1) + RTN_INDX(kxU2) +
        PROG_TXT(Cn) + RSLT_TXT(Cn) + PATG_NUM(1) + SPIN_MAP(Dn)
        """
        if len(data) < 7:  # Minimum for required fields
            raise RecordParsingError(
                cls.RECORD_TYPE, cls.RECORD_SUBTYPE,
                f"Insufficient data for FTR record: {len(data)} bytes",
                position=position
            )

        try:
            offset = 0

            # Parse basic required fields (Intel CPU little-endian format)
            test_num, head_num, site_num, test_flg = struct.unpack(
                '<IBBB', data[offset:offset+7]
            )
            offset += 7

            # Parse enhanced execution fields with defaults
            opt_flag = 0
            cyc_cnt = 0
            rel_vadr = 0
            rpt_cnt = 0
            num_fail = 0
            xfail_ad = 0
            yfail_ad = 0

            # Parse optional flag
            if offset + 1 <= len(data):
                opt_flag = struct.unpack('<B', data[offset:offset+1])[0]
                offset += 1

            # Parse execution fields
            if offset + 4 <= len(data):
                cyc_cnt = struct.unpack('<I', data[offset:offset+4])[0]
                offset += 4

            if offset + 4 <= len(data):
                rel_vadr = struct.unpack('<I', data[offset:offset+4])[0]
                offset += 4

            if offset + 4 <= len(data):
                rpt_cnt = struct.unpack('<I', data[offset:offset+4])[0]
                offset += 4

            if offset + 4 <= len(data):
                num_fail = struct.unpack('<I', data[offset:offset+4])[0]
                offset += 4

            if offset + 4 <= len(data):
                xfail_ad = struct.unpack('<I', data[offset:offset+4])[0]
                offset += 4

            if offset + 4 <= len(data):
                yfail_ad = struct.unpack('<I', data[offset:offset+4])[0]
                offset += 4

            # Parse enhanced timing fields
            vect_off = 0
            if offset + 4 <= len(data):
                vect_off = struct.unpack('<I', data[offset:offset+4])[0]
                offset += 4

            # Parse return bins array
            rtst_bin = []
            if offset + 1 <= len(data):
                rtn_icnt = struct.unpack('<B', data[offset:offset+1])[0]
                offset += 1

                # Parse array elements
                for i in range(rtn_icnt):
                    if offset + 2 <= len(data):
                        bin_val = struct.unpack('<H', data[offset:offset+2])[0]
                        rtst_bin.append(bin_val)
                        offset += 2

            # Parse enhanced string fields
            prog_txt = ""
            if offset < len(data):
                prog_txt, offset = parse_variable_length_string(data, offset)
                prog_txt = prog_txt or ""

            rslt_txt = ""
            if offset < len(data):
                rslt_txt, offset = parse_variable_length_string(data, offset)
                rslt_txt = rslt_txt or ""

            # Parse pattern generator number
            patg_num = 0
            if offset + 1 <= len(data):
                patg_num = struct.unpack('<B', data[offset:offset+1])[0]
                offset += 1

            # Parse spin map binary data (remaining bytes)
            spin_map = b""
            if offset < len(data):
                spin_map = data[offset:]

            return cls(
                record_type=cls.RECORD_TYPE,
                record_subtype=cls.RECORD_SUBTYPE,
                record_length=len(data),
                file_position=position,
                test_num=test_num,
                head_num=head_num,
                site_num=site_num,
                test_flg=test_flg,
                opt_flag=opt_flag,
                cyc_cnt=cyc_cnt,
                rel_vadr=rel_vadr,
                rpt_cnt=rpt_cnt,
                num_fail=num_fail,
                xfail_ad=xfail_ad,
                yfail_ad=yfail_ad,
                vect_off=vect_off,
                rtst_bin=rtst_bin,
                prog_txt=prog_txt,
                rslt_txt=rslt_txt,
                patg_num=patg_num,
                spin_map=spin_map
            )

        except (struct.error, ValueError) as e:
            raise RecordParsingError(
                cls.RECORD_TYPE, cls.RECORD_SUBTYPE,
                f"Failed to parse FTR record: {e}",
                position=position
            )

    def is_passing(self) -> bool:
        """Determine if this functional test passed."""
        return STDFConstants.is_pass_result(self.test_flg)

    def is_failing(self) -> bool:
        """Determine if this functional test failed."""
        return STDFConstants.is_fail_result(self.test_flg)

    def get_failure_count(self) -> int:
        """Get number of failures in this functional test."""
        return self.num_fail

    @property
    def is_priority_record(self) -> bool:
        """FTR is a priority record requiring complete field extraction."""
        return True

    @property
    def is_enhanced_record(self) -> bool:
        """FTR is an enhanced record with complete field access."""
        return True

    @property
    def record_name(self) -> str:
        """Return record name."""
        return "FTR"

    def get_enhanced_field_dict(self) -> Dict[str, Any]:
        """Get all enhanced fields as dictionary."""
        return {
            'test_num': self.test_num,
            'head_num': self.head_num,
            'site_num': self.site_num,
            'test_flg': self.test_flg,
            'opt_flag': self.opt_flag,
            'cyc_cnt': self.cyc_cnt,
            'rel_vadr': self.rel_vadr,
            'rpt_cnt': self.rpt_cnt,
            'num_fail': self.num_fail,
            'xfail_ad': self.xfail_ad,
            'yfail_ad': self.yfail_ad,
            'vect_off': self.vect_off,
            'rtst_bin': self.rtst_bin,
            'prog_txt': self.prog_txt,
            'rslt_txt': self.rslt_txt,
            'patg_num': self.patg_num,
            'spin_map': self.spin_map
        }

    def get_failure_rate(self) -> float:
        """Get failure rate as proportion."""
        if self.rpt_cnt > 0:
            return self.num_fail / self.rpt_cnt
        return 0.0

    def has_failures(self) -> bool:
        """Check if test has any failures."""
        return self.num_fail > 0

    def get_effective_cycle_count(self) -> int:
        """Get effective cycle count including vector offset."""
        return self.cyc_cnt + self.vect_off

    def get_cycles_per_repeat(self) -> float:
        """Get cycles per repeat count."""
        if self.rpt_cnt > 0:
            return self.cyc_cnt / self.rpt_cnt
        return self.cyc_cnt

    def get_failure_coordinates(self) -> tuple:
        """Get failure coordinates as (x, y) tuple."""
        return (self.xfail_ad, self.yfail_ad)

    def has_address_failures(self) -> bool:
        """Check if there are address-based failures."""
        return self.xfail_ad != 0 or self.yfail_ad != 0

    def get_test_summary(self) -> Dict[str, Any]:
        """Get comprehensive test summary."""
        return {
            'test_number': self.test_num,
            'test_name': self.prog_txt or f"Functional_Test_{self.test_num}",
            'site': f"Head {self.head_num}, Site {self.site_num}",
            'cycles': self.cyc_cnt,
            'failures': self.get_failure_count(),
            'passing': self.is_passing(),
            'pattern_generator': self.patg_num,
            'result_text': self.rslt_txt
        }


@dataclass
class MPRRecord(STDFV4Record):
    """
    Multiple-Result Parametric Record (MPR) - Type 15, Subtype 15.

    Contains multiple parametric test results in a single record.
    """

    test_num: int
    head_num: int
    site_num: int
    test_flg: int
    parm_flg: int
    rtn_icnt: int
    rslt_cnt: int
    rtn_stat: Optional[bytes] = None
    rtn_rslt: Optional[List[float]] = None
    test_txt: Optional[str] = None
    alarm_id: Optional[str] = None
    opt_flag: Optional[int] = None
    res_scal: Optional[int] = None
    llm_scal: Optional[int] = None
    hlm_scal: Optional[int] = None
    lo_limit: Optional[float] = None
    hi_limit: Optional[float] = None
    start_in: Optional[float] = None
    incr_in: Optional[float] = None
    rtn_indx: Optional[List[int]] = None
    units: Optional[str] = None
    units_in: Optional[str] = None
    c_resfmt: Optional[str] = None
    c_llmfmt: Optional[str] = None
    c_hlmfmt: Optional[str] = None
    lo_spec: Optional[float] = None
    hi_spec: Optional[float] = None

    RECORD_TYPE: ClassVar[int] = 15
    RECORD_SUBTYPE: ClassVar[int] = 15
    RECORD_NAME: ClassVar[str] = "MPR"

    @classmethod
    def parse(cls, data: bytes, endian: str, position: int) -> 'MPRRecord':
        """
        Parse MPR record from binary data.

        This is a simplified implementation focusing on core fields.
        """
        if len(data) < 10:  # Minimum for required fields
            raise RecordParsingError(
                cls.RECORD_TYPE, cls.RECORD_SUBTYPE,
                f"Insufficient data for MPR record: {len(data)} bytes",
                position=position
            )

        try:
            offset = 0

            # Parse required fields
            format_str = cls.create_struct_format(endian, 'IBBBBHH')
            test_num, head_num, site_num, test_flg, parm_flg, rtn_icnt, rslt_cnt = struct.unpack(
                format_str, data[offset:offset+12]
            )
            offset += 12

            # Parse results array (simplified)
            rtn_rslt = []
            if rslt_cnt > 0 and offset + (rslt_cnt * 4) <= len(data):
                for i in range(rslt_cnt):
                    result = struct.unpack(cls.create_struct_format(endian, 'f'),
                                         data[offset:offset+4])[0]
                    rtn_rslt.append(result)
                    offset += 4

            return cls(
                record_type=cls.RECORD_TYPE,
                record_subtype=cls.RECORD_SUBTYPE,
                record_length=len(data),
                file_position=position,
                test_num=test_num,
                head_num=head_num,
                site_num=site_num,
                test_flg=test_flg,
                parm_flg=parm_flg,
                rtn_icnt=rtn_icnt,
                rslt_cnt=rslt_cnt,
                rtn_rslt=rtn_rslt
            )

        except (struct.error, ValueError) as e:
            raise RecordParsingError(
                cls.RECORD_TYPE, cls.RECORD_SUBTYPE,
                f"Failed to parse MPR record: {e}",
                position=position
            )

    def is_passing(self) -> bool:
        """Determine if this test passed."""
        return STDFConstants.is_pass_result(self.test_flg)

    def get_result_count(self) -> int:
        """Get number of results in this record."""
        return len(self.rtn_rslt) if self.rtn_rslt else 0

    def get_results_summary(self) -> Dict[str, Any]:
        """Get summary of all results."""
        if not self.rtn_rslt:
            return {'count': 0, 'results': []}

        return {
            'count': len(self.rtn_rslt),
            'results': self.rtn_rslt,
            'min': min(self.rtn_rslt),
            'max': max(self.rtn_rslt),
            'avg': sum(self.rtn_rslt) / len(self.rtn_rslt)
        }


# Register record classes with factory
def register_test_records():
    """Register test record classes with the record factory."""
    from .base import RecordFactory

    RecordFactory.register_record_class(
        PTRRecord.RECORD_TYPE, PTRRecord.RECORD_SUBTYPE, PTRRecord
    )
    RecordFactory.register_record_class(
        FTRRecord.RECORD_TYPE, FTRRecord.RECORD_SUBTYPE, FTRRecord
    )
    RecordFactory.register_record_class(
        MPRRecord.RECORD_TYPE, MPRRecord.RECORD_SUBTYPE, MPRRecord
    )


# Auto-register when module is imported
register_test_records()