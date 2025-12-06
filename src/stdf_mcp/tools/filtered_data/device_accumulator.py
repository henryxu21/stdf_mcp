"""
MultiSiteDeviceAccumulator for accumulating test results with multi-site parallel testing support.

This module provides the MultiSiteDeviceAccumulator class that processes STDF records
with site-keyed tracking to correctly handle parallel multi-site testing scenarios
where multiple PIRs exist before any PRRs.

CRITICAL: This implementation fixes the multi-site parallel testing issue where
real-world STDF files have interleaved PTR records from multiple sites testing
simultaneously. Each PIR creates a NEW device entry (row in Excel), not grouped
by (device_id, site) across the entire file.

Pattern: For 10 DUTs × 2 sites = 20 rows expected, not 2 rows.
"""

from datetime import datetime
from typing import Dict, List, Optional, Set

from stdf_mcp.tools.filtered_data.models import DeviceTestResults


class MultiSiteDeviceAccumulator:
    """
    Accumulates test results handling parallel multi-site testing.

    Key Insight: Each PIR represents a separate part (row in Excel)
    - PIR site_num field identifies which site this part is from
    - Multiple PIRs can exist before any PRR (parallel testing)
    - PTR site_num field determines which PIR's data to update

    Workflow:
    1. PIR record creates NEW device context (not reuses)
    2. PTR records update device matching PTR's site_num
    3. PRR records finalize device matching PRR's site_num

    Memory Management:
    - Active devices: Only holds 2-4 devices simultaneously (one per site)
    - Completed list: Grows linearly with total parts
    - Memory footprint: ~200 bytes per device + ~20 bytes per test result

    Example STDF Sequence (Parallel Multi-Site):
        PIR #1 (Site 1, DUT 1)
        PIR #2 (Site 2, DUT 1)
          PTR (Site 1, Test P01500)  <- Routes to PIR #1 device
          PTR (Site 2, Test P01500)  <- Routes to PIR #2 device
          PTR (Site 1, Test P01200)  <- Routes to PIR #1 device
          PTR (Site 2, Test P01200)  <- Routes to PIR #2 device
          ... (all 8 tests interleaved)
        PRR #1 (Site 1)  <- Completes PIR #1 device
        PRR #2 (Site 2)  <- Completes PIR #2 device
        PIR #3 (Site 1, DUT 2)  <- New device for Site 1
        PIR #4 (Site 2, DUT 2)  <- New device for Site 2
        ... (repeat pattern)

    Result: For 10 DUTs × 2 sites = 20 rows (10 iterations × 2 sites)
    - Row 1: DUT 1, Site 1, all 8 test results
    - Row 2: DUT 1, Site 2, all 8 test results
    - Row 3: DUT 2, Site 1, all 8 test results
    - Row 4: DUT 2, Site 2, all 8 test results
    """

    def __init__(self, filtered_test_params: Set[str]) -> None:
        """
        Initialize accumulator with filtered test parameter set.

        Args:
            filtered_test_params: Set of test parameter names to accumulate
                                 (e.g., {"_P01500_POUT_NV_VXXX", "_P01200_POUT_NV_VXXX"})
        """
        # Track active devices by PIR site_num
        # Key: site_num (int) -> Value: DeviceTestResults (current device for this site)
        self.active_devices: Dict[int, DeviceTestResults] = {}

        # List of completed devices in chronological order (PRR order)
        self.completed_devices: List[DeviceTestResults] = []

        # Set of filtered test parameter names for fast lookup
        self.filtered_params = filtered_test_params

    def process_pir(
        self,
        device_id: str,
        site: int,
        head: int,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """
        Start new device context for this site (from PIR record).

        Each PIR creates a NEW device entry. If there's already an active device
        for this site (previous PIR without PRR), auto-complete it first.

        Args:
            device_id: Package device ID (part_id from PIR)
            site: Test site number (0-255)
            head: Test head number
            timestamp: Test execution time (optional)
        """
        # Check if there's already an active device for this site
        if site in self.active_devices:
            # Previous device on this site not completed - auto-complete it
            # This handles malformed STDF files with consecutive PIRs
            self.completed_devices.append(self.active_devices[site])

        # Create NEW device entry for this site
        self.active_devices[site] = DeviceTestResults(
            device_id=device_id,
            site=site,
            head=head,
            timestamp=timestamp,
            test_results={},  # Empty dict for sparse data
        )

    def process_ptr(
        self, ptr_site: int, test_name: str, test_result: Optional[float]
    ) -> None:
        """
        Add test result to device matching PTR's site (from PTR/FTR record).

        PTR routing uses PTR's own site_num field to find the target device.
        This correctly handles interleaved PTRs from multiple sites.

        Args:
            ptr_site: Site number from PTR record (ptr.site_num)
            test_name: Test parameter name
            test_result: Measured test result value

        Returns:
            None (silently skips if PTR without matching PIR or parameter not in filter)
        """
        # Find the active device for this site
        if ptr_site not in self.active_devices:
            # PTR without matching PIR: skip (data quality issue)
            return

        # Check if this test parameter is in filtered set
        if test_name not in self.filtered_params:
            # Parameter not in filter: skip
            return

        # Add test result to the device for this site
        self.active_devices[ptr_site].test_results[test_name] = test_result

    def process_prr(self, prr_site: int, part_id: str = "") -> None:
        """
        Complete device for this site (from PRR record).

        Updates device_id from PRR part_id before marking device complete.
        This fixes the issue where device_id was incorrectly extracted from
        PIR records (which don't have part_id field).

        Args:
            prr_site: Test site number from PRR (0-255)
            part_id: Device identifier from PRR part_id field.
                     Empty string if not present or null in STDF file.

        Behavior:
            - If part_id is non-empty after stripping whitespace: Use actual value
            - If part_id is empty/whitespace: Set to "unknown"
            - Move completed device from active_devices to completed_devices
            - If no active device for site: Silently skip (handles malformed STDF)
        """
        # Find the active device for this site
        if prr_site not in self.active_devices:
            # PRR without matching PIR: skip (data quality issue)
            return

        # Update device_id from PRR part_id (critical fix for FR-001)
        device = self.active_devices[prr_site]
        if part_id and part_id.strip():
            device.device_id = part_id
        else:
            device.device_id = "unknown"

        # Complete this site's device
        self.completed_devices.append(device)
        del self.active_devices[prr_site]

    def get_completed_devices(self) -> List[DeviceTestResults]:
        """
        Return all completed devices in chronological order.

        Auto-completes any remaining active devices (incomplete data) before returning.

        Returns:
            List of DeviceTestResults in chronological order (PRR order)
        """
        # Auto-complete any remaining active devices (incomplete data)
        for site in sorted(self.active_devices.keys()):
            self.completed_devices.append(self.active_devices[site])
        self.active_devices.clear()

        return self.completed_devices

    @property
    def active_device_count(self) -> int:
        """Return count of currently active devices (for debugging/monitoring)."""
        return len(self.active_devices)

    @property
    def completed_device_count(self) -> int:
        """Return count of completed devices (for debugging/monitoring)."""
        return len(self.completed_devices)
