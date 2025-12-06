"""
FilterEngine for filtering test parameters by name pattern or test number.

This module provides the FilterEngine class that applies filter criteria to
test parameters extracted from STDF files.
"""

from typing import List, Optional, Pattern

from stdf_mcp.tools.filtered_data.models import (
    TestNumFilter,
    TestParameter,
)


class FilterEngine:
    """
    Engine for applying test identifier and site filters to test parameters.

    Supports:
    - Test name filtering using regex patterns
    - Test number filtering using series/range/mixed inputs
    - Site number filtering (single/multiple sites or all sites)
    """

    def matches_site(
        self, site_num: int, site_filter: Optional[List[int]] = None
    ) -> bool:
        """
        Check if a site number matches the site filter criteria.

        Args:
            site_num: Site number from PTR/FTR record (0-255)
            site_filter: Optional list of site numbers to include.
                        If None, all sites match (no filtering).

        Returns:
            True if site should be included, False otherwise

        Examples:
            >>> engine = FilterEngine()
            >>> engine.matches_site(1, None)  # No filter - all sites
            True
            >>> engine.matches_site(1, [1, 2])  # Site 1 in filter
            True
            >>> engine.matches_site(3, [1, 2])  # Site 3 not in filter
            False
        """
        if site_filter is None:
            # No site filter specified - include all sites
            return True

        # Check if site_num is in the filter list
        return site_num in site_filter

    def apply_test_name_filter(
        self, parameters: List[TestParameter], pattern: Pattern[str]
    ) -> List[TestParameter]:
        """
        Filter test parameters by name using regex pattern.

        Args:
            parameters: List of test parameters to filter
            pattern: Compiled regex pattern to match against test_name

        Returns:
            Filtered list of test parameters matching the pattern
        """
        filtered = []
        for param in parameters:
            if pattern.search(param.test_name):
                filtered.append(param)
        return filtered

    def apply_test_num_filter(
        self, parameters: List[TestParameter], test_filter: TestNumFilter
    ) -> List[TestParameter]:
        """
        Filter test parameters by test number using TestNumFilter.

        Args:
            parameters: List of test parameters to filter
            test_filter: TestNumFilter with series/range criteria

        Returns:
            Filtered list of test parameters matching the test_num filter
        """
        filtered = []
        seen_test_nums = set()  # Deduplicate overlapping series/ranges

        for param in parameters:
            # Check if test_num matches filter
            if test_filter.matches(param.test_number):
                # Avoid duplicates (series and range may overlap)
                if param.test_number not in seen_test_nums:
                    filtered.append(param)
                    seen_test_nums.add(param.test_number)

        return filtered

    def get_filtered_parameters(
        self,
        all_parameters: List[TestParameter],
        test_name_pattern: Optional[Pattern[str]] = None,
        test_num_filter: Optional[TestNumFilter] = None,
    ) -> List[TestParameter]:
        """
        Apply appropriate filter to test parameters.

        Args:
            all_parameters: Complete list of test parameters from STDF
            test_name_pattern: Optional regex pattern for test name filtering
            test_num_filter: Optional TestNumFilter for test number filtering

        Returns:
            Filtered list of test parameters

        Raises:
            ValueError: If neither or both filters are specified
        """
        if not test_name_pattern and not test_num_filter:
            raise ValueError(
                "Must specify either test_name_pattern or test_num_filter"
            )

        if test_name_pattern and test_num_filter:
            raise ValueError(
                "Cannot specify both test_name_pattern and test_num_filter"
            )

        # Apply appropriate filter
        if test_name_pattern:
            return self.apply_test_name_filter(
                all_parameters, test_name_pattern
            )
        else:
            # At this point, test_num_filter is guaranteed to be non-None
            # due to the validation checks above
            assert test_num_filter is not None
            return self.apply_test_num_filter(all_parameters, test_num_filter)
