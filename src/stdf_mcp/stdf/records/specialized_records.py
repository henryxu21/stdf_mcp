"""
Specialized STDF record implementations for priority record types.

Contains implementations for BPS, DTR, GDR, RDR, and SDR records that require
complete field extraction according to the two-tier STDF record handling approach.

All records follow Intel CPU little-endian parsing with comprehensive field access.
"""

import struct
from dataclasses import dataclass, field
from typing import List, Any, Tuple, Optional, ClassVar, Dict
from .base import STDFV4Record
from ..exceptions import RecordParsingError


def parse_cn_string(data: bytes, offset: int) -> Tuple[str, int]:
    """Parse STDF Cn (variable-length string) field with error handling."""
    if offset >= len(data):
        return "", offset

    str_len = data[offset] if offset < len(data) else 0
    offset += 1

    if str_len == 0 or offset + str_len > len(data):
        return "", offset

    try:
        string_data = data[offset:offset + str_len].decode('ascii', errors='replace')
        return string_data, offset + str_len
    except (UnicodeDecodeError, IndexError):
        return "", min(offset + str_len, len(data))


def parse_array_field(data: bytes, offset: int, element_size: int, count: int) -> Tuple[List, int]:
    """Parse STDF array field (xU1, xU2, xU4) with bounds checking."""
    elements = []
    format_map = {1: '<B', 2: '<H', 4: '<I'}
    fmt = format_map.get(element_size, '<B')

    for i in range(count):
        if offset + element_size > len(data):
            break

        try:
            elements.append(struct.unpack(fmt, data[offset:offset+element_size])[0])
        except struct.error:
            break

        offset += element_size

    return elements, offset


@dataclass
class BPSRecord(STDFV4Record):
    """Begin Program Section Record - Marks beginning of a program section"""
    seq_name: str = ""     # Section name (Cn)
    raw_data: bytes = b""  # Raw binary data

    RECORD_TYPE: ClassVar[int] = 20
    RECORD_SUBTYPE: ClassVar[int] = 10
    RECORD_NAME: ClassVar[str] = "BPS"

    @classmethod
    def parse(cls, data: bytes, position: int) -> 'BPSRecord':
        """Parse BPS record (simple string record)"""
        seq_name, _ = parse_cn_string(data, 0)

        return cls(
            record_type=20,
            record_subtype=10,
            record_length=len(data),
            file_position=position,
            seq_name=seq_name,
            raw_data=data
        )

    @property
    def is_priority_record(self) -> bool:
        """BPS is a priority record requiring complete field extraction."""
        return True

    @property
    def record_name(self) -> str:
        """Return record name."""
        return "BPS"

    def get_field_dict(self) -> Dict[str, Any]:
        """Get all fields as dictionary."""
        return {
            'record_type': self.record_type,
            'record_subtype': self.record_subtype,
            'seq_name': self.seq_name
        }


@dataclass
class DTRRecord(STDFV4Record):
    """Datalog Text Record - Contains ASCII information from datalog"""
    text_dat: str = ""     # Datalog information (Cn)
    raw_data: bytes = b""  # Raw binary data

    RECORD_TYPE: ClassVar[int] = 1
    RECORD_SUBTYPE: ClassVar[int] = 60
    RECORD_NAME: ClassVar[str] = "DTR"

    @classmethod
    def parse(cls, data: bytes, position: int) -> 'DTRRecord':
        """Parse DTR record (simple text record)"""
        text_dat, _ = parse_cn_string(data, 0)

        return cls(
            record_type=50,
            record_subtype=30,
            record_length=len(data),
            file_position=position,
            text_dat=text_dat,
            raw_data=data
        )

    @property
    def is_priority_record(self) -> bool:
        """DTR is a priority record requiring complete field extraction."""
        return True

    @property
    def record_name(self) -> str:
        """Return record name."""
        return "DTR"

    def get_field_dict(self) -> Dict[str, Any]:
        """Get all fields as dictionary."""
        return {
            'record_type': self.record_type,
            'record_subtype': self.record_subtype,
            'text_dat': self.text_dat
        }


@dataclass
class GDRRecord(STDFV4Record):
    """Generic Data Record - Contains tool-specific generic data"""
    fld_cnt: int = 0       # Count of fields in record (U2)
    gen_data: bytes = b""  # Generic data (Vn - variable type)
    raw_data: bytes = b""  # Raw binary data

    RECORD_TYPE: ClassVar[int] = 50
    RECORD_SUBTYPE: ClassVar[int] = 10
    RECORD_NAME: ClassVar[str] = "GDR"

    @classmethod
    def parse(cls, data: bytes, position: int) -> 'GDRRecord':
        """Parse GDR record with flexible data handling"""
        if len(data) < 2:
            raise RecordParsingError(50, 10, "GDR record too short", position)

        fld_cnt = struct.unpack('<H', data[:2])[0]
        gen_data = data[2:]  # Remaining data as generic

        return cls(
            record_type=50,
            record_subtype=10,
            record_length=len(data),
            file_position=position,
            fld_cnt=fld_cnt,
            gen_data=gen_data,
            raw_data=data
        )

    def decode_generic_fields(self) -> List[Any]:
        """Attempt to decode generic data based on field count"""
        # Implementation depends on specific ATE vendor format
        # Returns list of decoded field values
        return []

    @property
    def is_priority_record(self) -> bool:
        """GDR is a priority record requiring complete field extraction."""
        return True

    @property
    def record_name(self) -> str:
        """Return record name."""
        return "GDR"

    def get_field_dict(self) -> Dict[str, Any]:
        """Get all fields as dictionary."""
        return {
            'record_type': self.record_type,
            'record_subtype': self.record_subtype,
            'fld_cnt': self.fld_cnt,
            'gen_data': self.gen_data
        }


@dataclass
class RDRRecord(STDFV4Record):
    """Retest Data Record - Signals that data was collected in retest mode"""
    num_bins: int = 0      # Number of bins (U2)
    rtst_bin: List[int] = field(default_factory=list)  # Array of retest bin numbers (xU2)
    raw_data: bytes = b""  # Raw binary data

    RECORD_TYPE: ClassVar[int] = 1
    RECORD_SUBTYPE: ClassVar[int] = 70
    RECORD_NAME: ClassVar[str] = "RDR"

    @classmethod
    def parse(cls, data: bytes, position: int) -> 'RDRRecord':
        """Parse RDR record with array handling"""
        if len(data) < 2:
            raise RecordParsingError(1, 70, "RDR record too short", position)

        num_bins = struct.unpack('<H', data[:2])[0]
        rtst_bin, _ = parse_array_field(data, 2, element_size=2, count=num_bins)

        return cls(
            record_type=1,
            record_subtype=70,
            record_length=len(data),
            file_position=position,
            num_bins=num_bins,
            rtst_bin=rtst_bin,
            raw_data=data
        )

    @property
    def is_priority_record(self) -> bool:
        """RDR is a priority record requiring complete field extraction."""
        return True

    @property
    def record_name(self) -> str:
        """Return record name."""
        return "RDR"

    def get_field_dict(self) -> Dict[str, Any]:
        """Get all fields as dictionary."""
        return {
            'record_type': self.record_type,
            'record_subtype': self.record_subtype,
            'num_bins': self.num_bins,
            'rtst_bin': self.rtst_bin
        }


@dataclass
class SDRRecord(STDFV4Record):
    """Site Description Record - Contains test site configuration information"""

    # Fixed fields
    head_num: int = 0      # Test head number (U1)
    site_grp: int = 0      # Site group number (U1)
    site_cnt: int = 0      # Number of test sites (U1)
    site_num: List[int] = field(default_factory=list)  # Array of site numbers (xU1)

    # Complete string fields for hardware configuration
    hand_typ: str = ""     # Handler type (Cn)
    hand_id: str = ""      # Handler ID (Cn)
    card_typ: str = ""     # Card type (Cn)
    card_id: str = ""      # Card ID (Cn)
    load_typ: str = ""     # Load board type (Cn)
    load_id: str = ""      # Load board ID (Cn)
    dib_typ: str = ""      # DIB type (Cn)
    dib_id: str = ""       # DIB ID (Cn)
    cabl_typ: str = ""     # Cable type (Cn)
    cabl_id: str = ""      # Cable ID (Cn)
    cont_typ: str = ""     # Contactor type (Cn)
    cont_id: str = ""      # Contactor ID (Cn)
    lasr_typ: str = ""     # Laser type (Cn)
    lasr_id: str = ""      # Laser ID (Cn)
    extr_typ: str = ""     # Extra type (Cn)
    extr_id: str = ""      # Extra ID (Cn)
    raw_data: bytes = b""  # Raw binary data

    RECORD_TYPE: ClassVar[int] = 1
    RECORD_SUBTYPE: ClassVar[int] = 80
    RECORD_NAME: ClassVar[str] = "SDR"

    @classmethod
    def parse(cls, data: bytes, position: int) -> 'SDRRecord':
        """Parse SDR record with complete hardware configuration"""
        if len(data) < 3:
            raise RecordParsingError(1, 80, "SDR record too short", position)

        # Parse fixed fields
        head_num, site_grp, site_cnt = struct.unpack('<BBB', data[:3])

        # Parse site number array
        offset = 3
        site_num, offset = parse_array_field(data, offset, element_size=1, count=site_cnt)

        # Parse all string fields
        string_fields = {}
        field_names = [
            'hand_typ', 'hand_id', 'card_typ', 'card_id', 'load_typ', 'load_id',
            'dib_typ', 'dib_id', 'cabl_typ', 'cabl_id', 'cont_typ', 'cont_id',
            'lasr_typ', 'lasr_id', 'extr_typ', 'extr_id'
        ]

        for field_name in field_names:
            if offset >= len(data):
                string_fields[field_name] = ""
            else:
                string_value, offset = parse_cn_string(data, offset)
                string_fields[field_name] = string_value

        return cls(
            record_type=1,
            record_subtype=80,
            record_length=len(data),
            file_position=position,
            head_num=head_num,
            site_grp=site_grp,
            site_cnt=site_cnt,
            site_num=site_num,
            raw_data=data,
            **string_fields
        )

    @property
    def is_priority_record(self) -> bool:
        """SDR is a priority record requiring complete field extraction."""
        return True

    @property
    def record_name(self) -> str:
        """Return record name."""
        return "SDR"

    def get_field_dict(self) -> Dict[str, Any]:
        """Get all fields as dictionary."""
        return {
            'record_type': self.record_type,
            'record_subtype': self.record_subtype,
            'head_num': self.head_num,
            'site_grp': self.site_grp,
            'site_cnt': self.site_cnt,
            'site_num': self.site_num,
            'hand_typ': self.hand_typ,
            'hand_id': self.hand_id,
            'card_typ': self.card_typ,
            'card_id': self.card_id,
            'load_typ': self.load_typ,
            'load_id': self.load_id,
            'dib_typ': self.dib_typ,
            'dib_id': self.dib_id,
            'cabl_typ': self.cabl_typ,
            'cabl_id': self.cabl_id,
            'cont_typ': self.cont_typ,
            'cont_id': self.cont_id,
            'lasr_typ': self.lasr_typ,
            'lasr_id': self.lasr_id,
            'extr_typ': self.extr_typ,
            'extr_id': self.extr_id
        }


# Register record classes with factory
def register_specialized_records():
    """Register specialized record classes with the record factory."""
    from .base import RecordFactory

    RecordFactory.register_record_class(
        BPSRecord.RECORD_TYPE, BPSRecord.RECORD_SUBTYPE, BPSRecord
    )
    RecordFactory.register_record_class(
        DTRRecord.RECORD_TYPE, DTRRecord.RECORD_SUBTYPE, DTRRecord
    )
    RecordFactory.register_record_class(
        GDRRecord.RECORD_TYPE, GDRRecord.RECORD_SUBTYPE, GDRRecord
    )
    RecordFactory.register_record_class(
        RDRRecord.RECORD_TYPE, RDRRecord.RECORD_SUBTYPE, RDRRecord
    )
    RecordFactory.register_record_class(
        SDRRecord.RECORD_TYPE, SDRRecord.RECORD_SUBTYPE, SDRRecord
    )


# Auto-register when module is imported
register_specialized_records()