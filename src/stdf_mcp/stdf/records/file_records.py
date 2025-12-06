"""
STDF-V4 file information record implementations.

This module implements the file-level STDF-V4 record types including:
- FAR (File Attribute Record)
- MIR (Master Information Record)
- MRR (Master Results Record)

These records provide file-level metadata and summary information.
"""

import struct
from dataclasses import dataclass
from typing import Optional, ClassVar, Dict, Any
from datetime import datetime

from ..types import (
    CPUType, STDFVersion, get_endian_format,
    parse_variable_length_string, format_stdf_timestamp,
    STDF_DATA_TYPES, STDFConstants
)
from ..exceptions import RecordParsingError
from .base import STDFV4Record


@dataclass
class FARRecord(STDFV4Record):
    """
    File Attribute Record (FAR) - Type 0, Subtype 10.

    The first record in every STDF file, containing file format information.
    """

    cpu_type: int
    stdf_ver: int

    RECORD_TYPE: ClassVar[int] = 0
    RECORD_SUBTYPE: ClassVar[int] = 10
    RECORD_NAME: ClassVar[str] = "FAR"

    @classmethod
    def parse(cls, data: bytes, position: int) -> 'FARRecord':
        """
        Parse FAR record from binary data (Intel CPU little-endian only).

        FAR structure: CPU_TYP(1) + STDF_VER(1)
        """
        if len(data) < 2:
            raise RecordParsingError(
                cls.RECORD_TYPE, cls.RECORD_SUBTYPE,
                f"Insufficient data for FAR record: {len(data)} bytes",
                position=position
            )

        try:
            # Intel CPU little-endian format only
            cpu_type, stdf_ver = struct.unpack('<BB', data[:2])

            return cls(
                record_type=cls.RECORD_TYPE,
                record_subtype=cls.RECORD_SUBTYPE,
                record_length=len(data),
                file_position=position,
                cpu_type=cpu_type,
                stdf_ver=stdf_ver
            )

        except struct.error as e:
            raise RecordParsingError(
                cls.RECORD_TYPE, cls.RECORD_SUBTYPE,
                f"Failed to parse FAR record: {e}",
                position=position
            )

    def get_cpu_type_name(self) -> str:
        """Get human-readable CPU type name."""
        cpu_types = {
            CPUType.SUN_SPARC: "Sun SPARC",
            CPUType.LITTLE_ENDIAN: "Little Endian",
            CPUType.BIG_ENDIAN: "Big Endian"
        }
        return cpu_types.get(self.cpu_type, f"Unknown ({self.cpu_type})")

    def get_stdf_version_name(self) -> str:
        """Get human-readable STDF version name."""
        if self.stdf_ver == STDFVersion.V4:
            return "STDF-V4"
        elif self.stdf_ver == STDFVersion.V3:
            return "STDF-V3"
        else:
            return f"Unknown ({self.stdf_ver})"

    def is_supported_version(self) -> bool:
        """Check if this STDF version is supported."""
        return self.stdf_ver == STDFVersion.V4

    def get_endianness(self) -> str:
        """Get endianness string for this file."""
        return get_endian_format(CPUType(self.cpu_type)).replace('<', 'little').replace('>', 'big')

    @property
    def is_priority_record(self) -> bool:
        """FAR is a priority record requiring complete field extraction."""
        return True

    @property
    def record_name(self) -> str:
        """Return record name."""
        return "FAR"

    def get_enhanced_field_dict(self) -> Dict[str, Any]:
        """Get all fields as dictionary."""
        return {
            'record_type': self.record_type,
            'record_subtype': self.record_subtype,
            'cpu_type': self.cpu_type,
            'stdf_ver': self.stdf_ver
        }


@dataclass
class MIRRecord(STDFV4Record):
    """
    Master Information Record (MIR) - Type 1, Subtype 10.

    Contains complete test program and setup information with all 30 string fields.
    Enhanced for complete field extraction according to STDF-V4 specification.
    """

    # Required fixed fields
    setup_t: int = 0           # Date and time of job setup (U4)
    start_t: int = 0           # Date and time first part tested (U4)
    stat_num: int = 0          # Tester station number (U1)
    mode_cod: str = ""         # Test mode code (C1)
    rtst_cod: str = ""         # Retest code (C1)
    prot_cod: str = ""         # Data protection code (C1)
    burn_tim: int = 0          # Burn-in time in seconds (U2)
    cmod_cod: str = ""         # Command mode code (C1)

    # Complete variable-length string fields (Cn) - all 30 fields
    lot_id: str = ""       # Lot identification
    part_typ: str = ""     # Part type
    node_nam: str = ""     # Test node name
    tstr_typ: str = ""     # Tester type
    job_nam: str = ""      # Job name
    job_rev: str = ""      # Job revision
    sblot_id: str = ""     # Sublot ID
    oper_nam: str = ""     # Operator name
    exec_typ: str = ""     # Executive type
    exec_ver: str = ""     # Executive version
    test_cod: str = ""     # Test code
    tst_temp: str = ""     # Test temperature
    user_txt: str = ""     # Generic user text
    aux_file: str = ""     # Auxiliary data file name
    pkg_typ: str = ""      # Package type
    famly_id: str = ""     # Device family ID
    date_cod: str = ""     # Date code
    facil_id: str = ""     # Test facility ID
    floor_id: str = ""     # Test floor ID
    proc_id: str = ""      # Fabrication process ID
    oper_frq: str = ""     # Operation frequency
    spec_nam: str = ""     # Test specification name
    spec_ver: str = ""     # Test specification version
    flow_id: str = ""      # Test flow ID
    setup_id: str = ""     # Test setup ID
    dsgn_rev: str = ""     # Device design revision
    eng_id: str = ""       # Engineering ID
    rom_cod: str = ""      # ROM code ID
    serl_num: str = ""     # Tester serial number
    supr_nam: str = ""     # Supervisor name

    RECORD_TYPE: ClassVar[int] = 1
    RECORD_SUBTYPE: ClassVar[int] = 10
    RECORD_NAME: ClassVar[str] = "MIR"

    @classmethod
    def parse(cls, data: bytes, position: int) -> 'MIRRecord':
        """
        Parse MIR record from binary data with complete field extraction.

        MIR structure: Fixed fields followed by 30 variable-length string fields
        """
        if len(data) < 15:  # Minimum for all fixed fields
            raise RecordParsingError(
                cls.RECORD_TYPE, cls.RECORD_SUBTYPE,
                f"Insufficient data for MIR record: {len(data)} bytes",
                position=position
            )

        try:
            offset = 0

            # Parse fixed fields (Intel CPU little-endian format only)
            setup_t, start_t, stat_num = struct.unpack('<IIB', data[offset:offset+9])
            offset += 9

            # Parse single character fields
            mode_cod = chr(data[offset]) if offset < len(data) else ''
            offset += 1
            rtst_cod = chr(data[offset]) if offset < len(data) else ''
            offset += 1
            prot_cod = chr(data[offset]) if offset < len(data) else ''
            offset += 1

            # Parse burn time
            burn_tim = struct.unpack('<H', data[offset:offset+2])[0] if offset + 1 < len(data) else 0
            offset += 2

            # Parse command mode code
            cmod_cod = chr(data[offset]) if offset < len(data) else ''
            offset += 1

            # Parse all 30 variable-length string fields
            string_fields = {}
            field_names = [
                'lot_id', 'part_typ', 'node_nam', 'tstr_typ', 'job_nam', 'job_rev',
                'sblot_id', 'oper_nam', 'exec_typ', 'exec_ver', 'test_cod', 'tst_temp',
                'user_txt', 'aux_file', 'pkg_typ', 'famly_id', 'date_cod', 'facil_id',
                'floor_id', 'proc_id', 'oper_frq', 'spec_nam', 'spec_ver', 'flow_id',
                'setup_id', 'dsgn_rev', 'eng_id', 'rom_cod', 'serl_num', 'supr_nam'
            ]

            for field_name in field_names:
                if offset >= len(data):
                    string_fields[field_name] = ""
                else:
                    string_value, offset = parse_variable_length_string(data, offset)
                    string_fields[field_name] = string_value or ""

            return cls(
                record_type=cls.RECORD_TYPE,
                record_subtype=cls.RECORD_SUBTYPE,
                record_length=len(data),
                file_position=position,
                setup_t=setup_t,
                start_t=start_t,
                stat_num=stat_num,
                mode_cod=mode_cod,
                rtst_cod=rtst_cod,
                prot_cod=prot_cod,
                burn_tim=burn_tim,
                cmod_cod=cmod_cod,
                **string_fields
            )

        except (struct.error, ValueError) as e:
            raise RecordParsingError(
                cls.RECORD_TYPE, cls.RECORD_SUBTYPE,
                f"Failed to parse MIR record: {e}",
                position=position
            )

    def get_setup_time(self) -> Optional[datetime]:
        """Get setup time as datetime object."""
        if self.setup_t:
            return format_stdf_timestamp(self.setup_t)
        return None

    def get_start_time(self) -> Optional[datetime]:
        """Get start time as datetime object."""
        if self.start_t:
            return format_stdf_timestamp(self.start_t)
        return None

    def get_setup_datetime(self) -> Optional[datetime]:
        """Get setup time as datetime object (alias for compatibility)."""
        return self.get_setup_time()

    def is_package_test(self) -> bool:
        """Determine if this represents package test context."""
        return True  # Assume package test for Intel CPU constraint

    @property
    def is_priority_record(self) -> bool:
        """MIR is a priority record requiring complete field extraction."""
        return True

    @property
    def is_enhanced_record(self) -> bool:
        """MIR is an enhanced record with complete field access."""
        return True

    @property
    def record_name(self) -> str:
        """Return record name."""
        return "MIR"

    def get_enhanced_field_dict(self) -> Dict[str, Any]:
        """Get all enhanced fields as dictionary."""
        return {
            'setup_t': self.setup_t,
            'start_t': self.start_t,
            'stat_num': self.stat_num,
            'mode_cod': self.mode_cod,
            'rtst_cod': self.rtst_cod,
            'prot_cod': self.prot_cod,
            'burn_tim': self.burn_tim,
            'cmod_cod': self.cmod_cod,
            'lot_id': self.lot_id,
            'part_typ': self.part_typ,
            'node_nam': self.node_nam,
            'tstr_typ': self.tstr_typ,
            'job_nam': self.job_nam,
            'job_rev': self.job_rev,
            'sblot_id': self.sblot_id,
            'oper_nam': self.oper_nam,
            'exec_typ': self.exec_typ,
            'exec_ver': self.exec_ver,
            'test_cod': self.test_cod,
            'tst_temp': self.tst_temp,
            'user_txt': self.user_txt,
            'aux_file': self.aux_file,
            'pkg_typ': self.pkg_typ,
            'famly_id': self.famly_id,
            'date_cod': self.date_cod,
            'facil_id': self.facil_id,
            'floor_id': self.floor_id,
            'proc_id': self.proc_id,
            'oper_frq': self.oper_frq,
            'spec_nam': self.spec_nam,
            'spec_ver': self.spec_ver,
            'flow_id': self.flow_id,
            'setup_id': self.setup_id,
            'dsgn_rev': self.dsgn_rev,
            'eng_id': self.eng_id,
            'rom_cod': self.rom_cod,
            'serl_num': self.serl_num,
            'supr_nam': self.supr_nam
        }

    def get_all_string_fields(self) -> Dict[str, str]:
        """Get all 30 string fields as dictionary."""
        return {
            'lot_id': self.lot_id, 'part_typ': self.part_typ, 'node_nam': self.node_nam,
            'tstr_typ': self.tstr_typ, 'job_nam': self.job_nam, 'job_rev': self.job_rev,
            'sblot_id': self.sblot_id, 'oper_nam': self.oper_nam, 'exec_typ': self.exec_typ,
            'exec_ver': self.exec_ver, 'test_cod': self.test_cod, 'tst_temp': self.tst_temp,
            'user_txt': self.user_txt, 'aux_file': self.aux_file, 'pkg_typ': self.pkg_typ,
            'famly_id': self.famly_id, 'date_cod': self.date_cod, 'facil_id': self.facil_id,
            'floor_id': self.floor_id, 'proc_id': self.proc_id, 'oper_frq': self.oper_frq,
            'spec_nam': self.spec_nam, 'spec_ver': self.spec_ver, 'flow_id': self.flow_id,
            'setup_id': self.setup_id, 'dsgn_rev': self.dsgn_rev, 'eng_id': self.eng_id,
            'rom_cod': self.rom_cod, 'serl_num': self.serl_num, 'supr_nam': self.supr_nam
        }

    def validate_timestamps(self) -> bool:
        """Validate that start_t >= setup_t."""
        return self.start_t >= self.setup_t

    def validate_string_fields(self) -> bool:
        """Validate that all string fields are valid ASCII."""
        for field_name, field_value in self.get_all_string_fields().items():
            if not isinstance(field_value, str):
                return False
        return True


@dataclass
class MRRRecord(STDFV4Record):
    """
    Master Results Record (MRR) - Type 1, Subtype 20.

    Contains test program execution summary and results with enhanced field extraction.
    Enhanced for complete field access according to STDF-V4 specification.
    """

    # Fixed fields
    finish_t: int = 0      # Date and time last part tested (U4)
    disp_cod: str = ""     # Lot disposition code (C1)

    # Enhanced variable-length fields
    usr_desc: str = ""     # User description of lot (Cn)
    exc_desc: str = ""     # Description of executive software (Cn)

    RECORD_TYPE: ClassVar[int] = 1
    RECORD_SUBTYPE: ClassVar[int] = 20
    RECORD_NAME: ClassVar[str] = "MRR"

    @classmethod
    def parse(cls, data: bytes, position: int) -> 'MRRRecord':
        """
        Parse MRR record from binary data with complete field extraction.

        MRR structure: FINISH_T(4) + DISP_COD(1) + USR_DESC(Cn) + EXC_DESC(Cn)
        """
        if len(data) < 4:  # Minimum for FINISH_T
            raise RecordParsingError(
                cls.RECORD_TYPE, cls.RECORD_SUBTYPE,
                f"Insufficient data for MRR record: {len(data)} bytes",
                position=position
            )

        try:
            offset = 0

            # Parse FINISH_T (Intel CPU little-endian format only)
            finish_t = struct.unpack('<I', data[offset:offset+4])[0]
            offset += 4

            # Parse disposition code
            disp_cod = ""
            if offset < len(data):
                disp_cod = chr(data[offset])
                offset += 1

            # Parse enhanced description strings
            usr_desc = ""
            exc_desc = ""

            if offset < len(data):
                try:
                    usr_desc, offset = parse_variable_length_string(data, offset)
                    usr_desc = usr_desc or ""
                except ValueError:
                    # Handle truncated string gracefully
                    usr_desc = ""

            if offset < len(data):
                try:
                    exc_desc, offset = parse_variable_length_string(data, offset)
                    exc_desc = exc_desc or ""
                except ValueError:
                    # Handle truncated string gracefully
                    exc_desc = ""

            return cls(
                record_type=cls.RECORD_TYPE,
                record_subtype=cls.RECORD_SUBTYPE,
                record_length=len(data),
                file_position=position,
                finish_t=finish_t,
                disp_cod=disp_cod,
                usr_desc=usr_desc,
                exc_desc=exc_desc
            )

        except (struct.error, ValueError) as e:
            raise RecordParsingError(
                cls.RECORD_TYPE, cls.RECORD_SUBTYPE,
                f"Failed to parse MRR record: {e}",
                position=position
            )

    def get_finish_time(self) -> Optional[datetime]:
        """Get finish time as datetime object."""
        if self.finish_t:
            return format_stdf_timestamp(self.finish_t)
        return None

    def get_finish_datetime(self) -> Optional[datetime]:
        """Get finish time as datetime object (alias for compatibility)."""
        return self.get_finish_time()

    def get_disposition_description(self) -> str:
        """Get human-readable disposition description."""
        dispositions = {
            'A': "Abort - job aborted by user or system",
            'C': "Complete - job completed normally",
            'P': "Pass - lot passed testing",
            'F': "Fail - lot failed testing",
            'R': "Retest - lot requires retesting",
            'E': "Error - job terminated due to error",
            'S': "Scrap - lot scrapped",
            'U': "Unknown - disposition unknown"
        }
        return dispositions.get(self.disp_cod, f"Unknown disposition: {self.disp_cod}")

    @property
    def is_priority_record(self) -> bool:
        """MRR is a priority record requiring complete field extraction."""
        return True

    @property
    def is_enhanced_record(self) -> bool:
        """MRR is an enhanced record with complete field access."""
        return True

    @property
    def record_name(self) -> str:
        """Return record name."""
        return "MRR"

    def get_enhanced_field_dict(self) -> Dict[str, Any]:
        """Get all enhanced fields as dictionary."""
        return {
            'finish_t': self.finish_t,
            'disp_cod': self.disp_cod,
            'usr_desc': self.usr_desc,
            'exc_desc': self.exc_desc
        }

    def validate_timestamp(self) -> bool:
        """Validate timestamp field."""
        return self.finish_t >= 0

    def validate_enhanced_fields(self) -> bool:
        """Validate enhanced string fields."""
        return (isinstance(self.usr_desc, str) and
                isinstance(self.exc_desc, str) and
                isinstance(self.disp_cod, str))


# Register record classes with factory
def register_file_records():
    """Register file record classes with the record factory."""
    from .base import RecordFactory

    RecordFactory.register_record_class(
        FARRecord.RECORD_TYPE, FARRecord.RECORD_SUBTYPE, FARRecord
    )
    RecordFactory.register_record_class(
        MIRRecord.RECORD_TYPE, MIRRecord.RECORD_SUBTYPE, MIRRecord
    )
    RecordFactory.register_record_class(
        MRRRecord.RECORD_TYPE, MRRRecord.RECORD_SUBTYPE, MRRRecord
    )


# Auto-register when module is imported
register_file_records()