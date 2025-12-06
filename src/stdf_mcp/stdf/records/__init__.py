"""
STDF-V4 records package initialization.

This module provides imports for all STDF-V4 record types and ensures
proper registration with the record factory.
"""

# Import all record modules to trigger registration
from .file_records import FARRecord, MIRRecord, MRRRecord
from .part_records import PIRRecord, PRRRecord
from .test_records import PTRRecord, FTRRecord, MPRRecord
from .summary_records import PCRRecord, HBRRecord, SBRRecord, TSRRecord
from .specialized_records import BPSRecord, DTRRecord, GDRRecord, RDRRecord, SDRRecord

# Import base classes
from .base import STDFV4Record, RecordFactory, UnknownRecord, NonPriorityRecord

# Export all record classes
__all__ = [
    # Base classes
    'STDFV4Record',
    'RecordFactory',
    'UnknownRecord',
    'NonPriorityRecord',

    # File records
    'FARRecord',
    'MIRRecord',
    'MRRRecord',

    # Part records
    'PIRRecord',
    'PRRRecord',

    # Test records
    'PTRRecord',
    'FTRRecord',
    'MPRRecord',

    # Summary records
    'PCRRecord',
    'HBRRecord',
    'SBRRecord',
    'TSRRecord',

    # Specialized records
    'BPSRecord',
    'DTRRecord',
    'GDRRecord',
    'RDRRecord',
    'SDRRecord'
]