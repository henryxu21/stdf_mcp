"""Statistical calculations for test time data.

This module provides statistical analysis functions for test execution times,
using population formulas per research decision #1.
"""

import statistics
from typing import List
from stdf_mcp.tools.test_time.models import TestTimeStatistics, TestTimeRecord


class TestTimeStatisticsCalculator:
    """Calculator for test time statistical metrics.

    Implements statistical calculations (min, max, mean, population std dev)
    for test execution time analysis.
    """

    def calculate(
        self,
        test_times: List[float],
        null_count: int = 0
    ) -> TestTimeStatistics:
        """Calculate statistics from test time values.

        Uses population standard deviation (÷N formula) since STDF contains
        complete population of tested devices, not a sample.

        Args:
            test_times: List of test time values in seconds (excludes None/nulls)
            null_count: Number of devices with missing test times

        Returns:
            TestTimeStatistics object with calculated metrics

        Raises:
            ValueError: If test_times is empty
        """
        if not test_times:
            raise ValueError("Cannot calculate statistics from empty test_times list")

        # Calculate min, max, mean
        min_seconds = self._calculate_min(test_times)
        max_seconds = self._calculate_max(test_times)
        mean_seconds = self._calculate_mean(test_times)

        # Calculate population standard deviation (÷N formula)
        std_dev_seconds = self._calculate_population_std_dev(test_times)

        return TestTimeStatistics(
            min_seconds=min_seconds,
            max_seconds=max_seconds,
            mean_seconds=mean_seconds,
            std_dev_seconds=std_dev_seconds,
            device_count=len(test_times),
            null_count=null_count,
        )

    def calculate_from_records(
        self,
        records: List[TestTimeRecord]
    ) -> TestTimeStatistics:
        """Calculate statistics from TestTimeRecord list.

        Convenience method that extracts test times from records and
        counts null values automatically.

        Args:
            records: List of TestTimeRecord objects

        Returns:
            TestTimeStatistics object with calculated metrics

        Raises:
            ValueError: If no valid test times found
        """
        # Extract valid test times (exclude None)
        valid_test_times = [
            r.test_time_seconds for r in records
            if r.test_time_seconds is not None
        ]

        # Count null test times
        null_count = sum(1 for r in records if r.test_time_seconds is None)

        if not valid_test_times:
            raise ValueError("No valid test times found. All devices have missing TEST_T.")

        return self.calculate(valid_test_times, null_count)

    def _calculate_min(self, test_times: List[float]) -> float:
        """Calculate minimum test time.

        Args:
            test_times: List of test time values

        Returns:
            Minimum value
        """
        return min(test_times)

    def _calculate_max(self, test_times: List[float]) -> float:
        """Calculate maximum test time.

        Args:
            test_times: List of test time values

        Returns:
            Maximum value
        """
        return max(test_times)

    def _calculate_mean(self, test_times: List[float]) -> float:
        """Calculate arithmetic mean (average) test time.

        Args:
            test_times: List of test time values

        Returns:
            Mean value (Σ(xi) / N)
        """
        return statistics.mean(test_times)

    def _calculate_population_std_dev(self, test_times: List[float]) -> float:
        """Calculate population standard deviation.

        Uses population formula: σ = sqrt(Σ(xi - μ)² / N)
        Note: Divides by N, not N-1 (population, not sample).

        Args:
            test_times: List of test time values

        Returns:
            Population standard deviation
        """
        if len(test_times) == 1:
            return 0.0  # Single value has zero variance

        # Use statistics.pstdev() for population standard deviation
        return statistics.pstdev(test_times)
