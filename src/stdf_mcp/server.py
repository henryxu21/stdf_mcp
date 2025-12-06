"""
STDF-V4 MCP Server implementation.

This module implements the Model Context Protocol (MCP) server for STDF-V4
file processing, providing 10 specialized tools for metadata extraction,
data analysis, filtering, statistics, and visualization.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

# MCP SDK imports
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource, Tool, TextContent, ImageContent, EmbeddedResource
)

# STDF imports
from .stdf.parser import STDFV4Parser, ParserConfig
from .stdf.stdf_data import STDFData
from .stdf.package_test import PackageTestAnalyzer
from .stdf.statistics import StatisticalAnalyzer
from .stdf.integrity import IntegrityValidator
from .stdf.converter import STDFConverter, convert_stdf_file
from .stdf.exceptions import STDFError, format_stdf_error


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class STDFMCPServer:
    """
    STDF-V4 MCP Server providing comprehensive STDF file analysis tools.

    Implements 10 specialized tools:
    1. validate_stdf_file - Validate STDF file format and integrity
    2. extract_metadata - Extract file and lot metadata
    3. extract_test_data - Extract test results and definitions
    4. extract_bin_data - Extract bin definitions and part counts
    5. extract_site_data - Extract test site information
    6. extract_yield_data - Extract yield statistics by site/bin
    7. extract_filtered_data - Filter data by various criteria
    8. calculate_statistics - Calculate comprehensive statistics
    9. generate_visualization - Generate charts and plots
    10. export_csv - Export data in CSV format
    """

    def __init__(self):
        """Initialize STDF MCP Server."""
        self.server = Server("stdf-v4-server")
        self.parser = STDFV4Parser()
        self._cached_stdf_data: Dict[str, STDFData] = {}
        self._setup_tools()
        self._setup_resources()

    def _setup_tools(self) -> None:
        """Setup MCP tools for STDF processing."""

        # Tool 1: Validate STDF file
        @self.server.call_tool()
        async def validate_stdf_file(file_path: str,
                                   strict_validation: bool = True) -> List[TextContent]:
            """
            Validate STDF file format, version, and integrity.

            Args:
                file_path: Path to STDF file
                strict_validation: Enable comprehensive integrity validation

            Returns:
                Validation results and file metadata
            """
            try:
                path = Path(file_path)
                if not path.exists():
                    return [TextContent(
                        type="text",
                        text=f"Error: File not found: {file_path}"
                    )]

                # Configure parser for strict validation
                config = ParserConfig(
                    enable_integrity_validation=strict_validation,
                    package_test_only=True
                )
                parser = STDFV4Parser(config)

                # Validate file format and structure
                validation_result = parser.get_file_validation_summary(path)

                result = {
                    "validation_status": "PASS" if validation_result.is_valid else "FAIL",
                    "file_info": {
                        "path": str(path),
                        "size_bytes": validation_result.file_size,
                        "stdf_version": validation_result.stdf_version,
                        "endianness": validation_result.endianness,
                        "estimated_records": validation_result.estimated_record_count
                    },
                    "validation_issues": validation_result.validation_issues,
                    "validated_at": datetime.now().isoformat()
                }

                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]

            except STDFError as e:
                error_msg = format_stdf_error(e, "File validation")
                return [TextContent(type="text", text=f"STDF Error: {error_msg}")]
            except Exception as e:
                logger.error(f"Validation error: {e}")
                return [TextContent(type="text", text=f"Error: {str(e)}")]

        # Tool 2: Extract metadata
        @self.server.call_tool()
        async def extract_metadata(file_path: str) -> List[TextContent]:
            """
            Extract file and lot metadata from STDF file.

            Args:
                file_path: Path to STDF file

            Returns:
                Comprehensive metadata including lot info, test program details
            """
            try:
                stdf_data = await self._load_stdf_file(file_path)

                metadata = {
                    "file_metadata": {
                        "path": str(stdf_data.file_metadata.file_path),
                        "size_bytes": stdf_data.file_metadata.file_size,
                        "stdf_version": stdf_data.file_metadata.stdf_version,
                        "endianness": stdf_data.file_metadata.endianness,
                        "record_count": stdf_data.file_metadata.record_count,
                        "parse_time_ms": stdf_data.file_metadata.parse_time_ms
                    },
                    "lot_metadata": {
                        "lot_id": stdf_data.lot_summary.lot_id,
                        "part_type": stdf_data.lot_summary.part_type,
                        "test_program": stdf_data.lot_summary.test_program,
                        "test_program_version": stdf_data.lot_summary.test_program_version,
                        "start_time": stdf_data.lot_summary.start_time.isoformat() if stdf_data.lot_summary.start_time else None,
                        "finish_time": stdf_data.lot_summary.finish_time.isoformat() if stdf_data.lot_summary.finish_time else None,
                        "total_parts": stdf_data.lot_summary.total_parts
                    },
                    "test_summary": stdf_data.get_test_summary(),
                    "extracted_at": datetime.now().isoformat()
                }

                return [TextContent(
                    type="text",
                    text=json.dumps(metadata, indent=2)
                )]

            except Exception as e:
                return [TextContent(type="text", text=f"Error: {str(e)}")]

        # Tool 3: Extract test data
        @self.server.call_tool()
        async def extract_test_data(file_path: str,
                                  test_numbers: Optional[List[int]] = None,
                                  limit: int = 1000) -> List[TextContent]:
            """
            Extract test results and definitions.

            Args:
                file_path: Path to STDF file
                test_numbers: Specific test numbers to extract (optional)
                limit: Maximum number of results per test

            Returns:
                Test definitions and results data
            """
            try:
                stdf_data = await self._load_stdf_file(file_path)

                # Filter test definitions
                test_defs_to_extract = stdf_data.test_definitions
                if test_numbers:
                    test_defs_to_extract = {
                        num: test_def for num, test_def in stdf_data.test_definitions.items()
                        if num in test_numbers
                    }

                # Extract test definitions
                test_definitions = {}
                for test_num, test_def in test_defs_to_extract.items():
                    test_definitions[test_num] = {
                        "test_number": test_def.test_num,
                        "test_name": test_def.test_name,
                        "test_type": test_def.test_type,
                        "units": test_def.units,
                        "low_limit": test_def.low_limit,
                        "high_limit": test_def.high_limit,
                        "execution_count": test_def.execution_count,
                        "failure_count": test_def.failure_count
                    }

                # Extract test results (limited)
                test_results = []
                result_count = 0
                for part in stdf_data.part_results:
                    if result_count >= limit:
                        break
                    for test_result in part.test_results:
                        if test_numbers is None or test_result.test_num in test_numbers:
                            test_results.append({
                                "test_number": test_result.test_num,
                                "part_id": test_result.part_id,
                                "site_id": test_result.site_id,
                                "result_value": test_result.result_value,
                                "units": test_result.units,
                                "passing": test_result.passing,
                                "within_limits": test_result.within_limits
                            })
                            result_count += 1
                            if result_count >= limit:
                                break

                result = {
                    "test_definitions": test_definitions,
                    "test_results": test_results,
                    "result_count": len(test_results),
                    "limit_applied": result_count >= limit,
                    "extracted_at": datetime.now().isoformat()
                }

                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]

            except Exception as e:
                return [TextContent(type="text", text=f"Error: {str(e)}")]

        # Tool 4: Extract bin data
        @self.server.call_tool()
        async def extract_bin_data(file_path: str) -> List[TextContent]:
            """
            Extract bin definitions and part count distributions.

            Args:
                file_path: Path to STDF file

            Returns:
                Hardware and software bin data with part counts
            """
            try:
                stdf_data = await self._load_stdf_file(file_path)

                # Extract hard bin data
                hard_bins = {}
                for bin_num, bin_def in stdf_data.hard_bins.items():
                    hard_bins[bin_num] = {
                        "bin_number": bin_def.bin_number,
                        "bin_name": bin_def.bin_name,
                        "bin_type": bin_def.bin_type,
                        "part_count": bin_def.part_count,
                        "is_pass_bin": bin_def.is_pass_bin,
                        "percentage": (bin_def.part_count / stdf_data.lot_summary.total_parts * 100.0)
                                    if stdf_data.lot_summary.total_parts > 0 else 0.0
                    }

                # Extract soft bin data
                soft_bins = {}
                for bin_num, bin_def in stdf_data.soft_bins.items():
                    soft_bins[bin_num] = {
                        "bin_number": bin_def.bin_number,
                        "bin_name": bin_def.bin_name,
                        "bin_type": bin_def.bin_type,
                        "part_count": bin_def.part_count,
                        "is_pass_bin": bin_def.is_pass_bin
                    }

                bin_summary = stdf_data.get_bin_summary()

                result = {
                    "hard_bins": hard_bins,
                    "soft_bins": soft_bins,
                    "bin_summary": bin_summary,
                    "extracted_at": datetime.now().isoformat()
                }

                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]

            except Exception as e:
                return [TextContent(type="text", text=f"Error: {str(e)}")]

        # Tool 5: Extract site data
        @self.server.call_tool()
        async def extract_site_data(file_path: str) -> List[TextContent]:
            """
            Extract test site information and statistics.

            Args:
                file_path: Path to STDF file

            Returns:
                Test site data including part counts and yields
            """
            try:
                stdf_data = await self._load_stdf_file(file_path)

                site_data = {}
                for site_id, site_info in stdf_data.test_sites.items():
                    site_data[site_id] = {
                        "head_number": site_info.head_num,
                        "site_number": site_info.site_num,
                        "site_description": site_info.site_description,
                        "total_parts_tested": site_info.total_parts_tested,
                        "passing_parts": site_info.passing_parts,
                        "failing_parts": site_info.failing_parts,
                        "yield_percent": (site_info.passing_parts / site_info.total_parts_tested * 100.0)
                                       if site_info.total_parts_tested > 0 else 0.0,
                        "retest_count": site_info.retest_count,
                        "abort_count": site_info.abort_count
                    }

                yield_by_site = stdf_data.get_yield_by_site()

                result = {
                    "test_sites": site_data,
                    "yield_by_site": yield_by_site,
                    "total_sites": len(site_data),
                    "active_sites": sum(1 for info in stdf_data.test_sites.values()
                                      if info.total_parts_tested > 0),
                    "extracted_at": datetime.now().isoformat()
                }

                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]

            except Exception as e:
                return [TextContent(type="text", text=f"Error: {str(e)}")]

        # Tool 6: Extract yield data
        @self.server.call_tool()
        async def extract_yield_data(file_path: str) -> List[TextContent]:
            """
            Extract comprehensive yield statistics.

            Args:
                file_path: Path to STDF file

            Returns:
                Yield data by site, bin, and overall statistics
            """
            try:
                stdf_data = await self._load_stdf_file(file_path)
                analyzer = PackageTestAnalyzer(stdf_data)

                yield_analysis = analyzer.analyze_yield()

                result = {
                    "overall_yield": yield_analysis.overall_yield,
                    "yield_by_site": yield_analysis.yield_by_site,
                    "yield_by_bin": yield_analysis.yield_by_bin,
                    "first_pass_yield": yield_analysis.first_pass_yield,
                    "final_yield": yield_analysis.final_yield,
                    "total_parts": stdf_data.lot_summary.total_parts,
                    "passing_parts": stdf_data.lot_summary.passing_parts,
                    "failing_parts": stdf_data.lot_summary.failing_parts,
                    "extracted_at": datetime.now().isoformat()
                }

                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]

            except Exception as e:
                return [TextContent(type="text", text=f"Error: {str(e)}")]

        # Tool 7: Extract filtered data
        @self.server.call_tool()
        async def extract_filtered_data(file_path: str,
                                       filter_criteria: str = "{}",
                                       limit: int = 1000) -> List[TextContent]:
            """
            Filter STDF data by various criteria.

            Args:
                file_path: Path to STDF file
                filter_criteria: JSON string with filter parameters
                limit: Maximum number of results to return

            Returns:
                Filtered data based on specified criteria
            """
            try:
                stdf_data = await self._load_stdf_file(file_path)

                # Parse filter criteria
                try:
                    filters = json.loads(filter_criteria)
                except json.JSONDecodeError:
                    filters = {}

                # Apply filters to parts
                filtered_parts = stdf_data.filter_parts_by_criteria(
                    passing=filters.get("passing"),
                    hard_bin=filters.get("hard_bin"),
                    site_id=filters.get("site_id"),
                    min_test_time=filters.get("min_test_time"),
                    max_test_time=filters.get("max_test_time")
                )

                # Limit results
                limited_parts = filtered_parts[:limit]

                # Format results
                results = []
                for part in limited_parts:
                    results.append({
                        "part_id": part.part_id,
                        "site_id": part.site_id,
                        "hard_bin": part.hard_bin,
                        "soft_bin": part.soft_bin,
                        "is_passing": part.is_passing,
                        "num_tests": part.num_tests,
                        "test_time_ms": part.test_time_ms,
                        "coordinates": part.get_coordinates()
                    })

                result = {
                    "filtered_parts": results,
                    "total_matches": len(filtered_parts),
                    "results_returned": len(results),
                    "filter_criteria": filters,
                    "limit_applied": len(filtered_parts) > limit,
                    "extracted_at": datetime.now().isoformat()
                }

                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]

            except Exception as e:
                return [TextContent(type="text", text=f"Error: {str(e)}")]

        # Tool 8: Calculate statistics
        @self.server.call_tool()
        async def calculate_statistics(file_path: str,
                                     test_numbers: Optional[List[int]] = None,
                                     analysis_type: str = "comprehensive") -> List[TextContent]:
            """
            Calculate comprehensive statistics for test data.

            Args:
                file_path: Path to STDF file
                test_numbers: Specific tests to analyze (optional)
                analysis_type: Type of analysis (basic, comprehensive, correlation)

            Returns:
                Statistical analysis results
            """
            try:
                stdf_data = await self._load_stdf_file(file_path)
                analyzer = StatisticalAnalyzer(stdf_data)

                if analysis_type == "basic":
                    # Basic statistics summary
                    result = analyzer.generate_statistical_summary()

                elif analysis_type == "comprehensive":
                    # Comprehensive analysis
                    yield_stats = analyzer.analyze_yield_statistics()

                    # Analyze specific tests or all tests
                    test_analyses = {}
                    tests_to_analyze = test_numbers or list(stdf_data.test_definitions.keys())[:10]

                    for test_num in tests_to_analyze:
                        if test_num in stdf_data.test_definitions:
                            test_analyses[test_num] = analyzer.analyze_test_statistics(test_num)

                    result = {
                        "yield_statistics": {
                            "overall_yield": yield_stats.overall_yield,
                            "yield_by_site": yield_stats.yield_by_site,
                            "yield_confidence_interval": yield_stats.yield_confidence_interval,
                            "yield_standard_error": yield_stats.yield_standard_error
                        },
                        "test_statistics": {
                            str(test_num): {
                                "test_name": analysis.test_name,
                                "descriptive_stats": {
                                    "count": analysis.descriptive_stats.count,
                                    "mean": analysis.descriptive_stats.mean,
                                    "median": analysis.descriptive_stats.median,
                                    "std_dev": analysis.descriptive_stats.std_dev,
                                    "min_value": analysis.descriptive_stats.min_value,
                                    "max_value": analysis.descriptive_stats.max_value,
                                    "skewness": analysis.descriptive_stats.skewness,
                                    "kurtosis": analysis.descriptive_stats.kurtosis
                                },
                                "pass_rate": analysis.pass_rate,
                                "within_limits_rate": analysis.within_limits_rate,
                                "cpk": analysis.cpk,
                                "cp": analysis.cp,
                                "sigma_level": analysis.sigma_level,
                                "distribution_type": analysis.distribution_analysis.distribution_type.value,
                                "outlier_count": analysis.distribution_analysis.outlier_count
                            }
                            for test_num, analysis in test_analyses.items()
                        }
                    }

                elif analysis_type == "correlation" and test_numbers and len(test_numbers) > 1:
                    # Correlation analysis
                    correlations = analyzer.calculate_correlation_matrix(test_numbers)

                    correlation_results = {}
                    for (test1, test2), corr_coeff in correlations.items():
                        key = f"{test1}_{test2}"
                        correlation_results[key] = {
                            "test1": test1,
                            "test2": test2,
                            "correlation_coefficient": corr_coeff,
                            "strength": "Strong" if abs(corr_coeff) > 0.7 else
                                       "Moderate" if abs(corr_coeff) > 0.3 else "Weak"
                        }

                    result = {
                        "correlation_analysis": correlation_results,
                        "test_numbers_analyzed": test_numbers
                    }

                else:
                    result = {"error": "Invalid analysis_type or insufficient test_numbers for correlation"}

                result["analysis_type"] = analysis_type
                result["calculated_at"] = datetime.now().isoformat()

                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2, default=str)
                )]

            except Exception as e:
                return [TextContent(type="text", text=f"Error: {str(e)}")]

        # Tool 9: Generate visualization
        @self.server.call_tool()
        async def generate_visualization(file_path: str,
                                       chart_type: str = "yield_by_site",
                                       test_number: Optional[int] = None,
                                       output_format: str = "json") -> List[TextContent]:
            """
            Generate visualization data for STDF analysis.

            Args:
                file_path: Path to STDF file
                chart_type: Type of chart (yield_by_site, test_histogram, bin_distribution, etc.)
                test_number: Specific test for test-related charts
                output_format: Output format (json, plotly, etc.)

            Returns:
                Visualization data or chart configuration
            """
            try:
                stdf_data = await self._load_stdf_file(file_path)

                if chart_type == "yield_by_site":
                    # Yield by site bar chart
                    yield_by_site = stdf_data.get_yield_by_site()

                    chart_data = {
                        "chart_type": "bar",
                        "title": "Yield by Test Site",
                        "x_axis": list(yield_by_site.keys()),
                        "y_axis": list(yield_by_site.values()),
                        "x_label": "Test Site",
                        "y_label": "Yield (%)",
                        "data_points": len(yield_by_site)
                    }

                elif chart_type == "bin_distribution":
                    # Bin distribution pie chart
                    bin_data = {}
                    for bin_num, bin_def in stdf_data.hard_bins.items():
                        if bin_def.part_count > 0:
                            bin_name = bin_def.bin_name or f"Bin {bin_num}"
                            bin_data[bin_name] = bin_def.part_count

                    chart_data = {
                        "chart_type": "pie",
                        "title": "Part Distribution by Hard Bin",
                        "labels": list(bin_data.keys()),
                        "values": list(bin_data.values()),
                        "total_parts": sum(bin_data.values())
                    }

                elif chart_type == "test_histogram" and test_number:
                    # Test result histogram
                    test_results = stdf_data.get_test_results_for_test(test_number)
                    values = [r.result_value for r in test_results if r.result_value is not None]

                    if values:
                        test_def = stdf_data.test_definitions.get(test_number)
                        test_name = test_def.test_name if test_def else f"Test {test_number}"

                        chart_data = {
                            "chart_type": "histogram",
                            "title": f"Distribution of {test_name}",
                            "values": values,
                            "x_label": test_def.units if test_def and test_def.units else "Value",
                            "y_label": "Frequency",
                            "data_points": len(values),
                            "low_limit": test_def.low_limit if test_def else None,
                            "high_limit": test_def.high_limit if test_def else None
                        }
                    else:
                        chart_data = {"error": f"No data found for test {test_number}"}

                elif chart_type == "test_failure_pareto":
                    # Test failure Pareto chart
                    analyzer = PackageTestAnalyzer(stdf_data)
                    top_failures = analyzer.get_top_failing_tests(10)

                    test_names = []
                    failure_rates = []
                    cumulative_impact = []
                    cumulative = 0

                    for failure in top_failures:
                        test_names.append(failure.test_name or f"Test {failure.test_number}")
                        failure_rates.append(failure.failure_rate)
                        cumulative += failure.failure_rate
                        cumulative_impact.append(cumulative)

                    chart_data = {
                        "chart_type": "pareto",
                        "title": "Top Failing Tests (Pareto Analysis)",
                        "x_axis": test_names,
                        "y_axis": failure_rates,
                        "cumulative": cumulative_impact,
                        "x_label": "Test Name",
                        "y_label": "Failure Rate (%)",
                        "data_points": len(test_names)
                    }

                else:
                    chart_data = {"error": f"Unsupported chart type: {chart_type}"}

                result = {
                    "visualization": chart_data,
                    "chart_type": chart_type,
                    "output_format": output_format,
                    "generated_at": datetime.now().isoformat()
                }

                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2, default=str)
                )]

            except Exception as e:
                return [TextContent(type="text", text=f"Error: {str(e)}")]

        # Tool 10: Export CSV
        @self.server.call_tool()
        async def export_csv(file_path: str,
                           export_type: str = "part_results",
                           include_headers: bool = True,
                           delimiter: str = ",") -> List[TextContent]:
            """
            Export STDF data in CSV format.

            Args:
                file_path: Path to STDF file
                export_type: Type of data to export (part_results, test_data, bin_data)
                include_headers: Include CSV headers
                delimiter: CSV delimiter character

            Returns:
                CSV formatted data
            """
            try:
                stdf_data = await self._load_stdf_file(file_path)

                csv_lines = []

                if export_type == "part_results":
                    # Export part results
                    if include_headers:
                        headers = [
                            "part_id", "site_id", "head_num", "site_num",
                            "hard_bin", "soft_bin", "is_passing", "num_tests",
                            "test_time_ms", "x_coord", "y_coord", "part_text"
                        ]
                        csv_lines.append(delimiter.join(headers))

                    for part in stdf_data.part_results:
                        row = [
                            part.part_id or "",
                            part.site_id,
                            str(part.head_num),
                            str(part.site_num),
                            str(part.hard_bin),
                            str(part.soft_bin) if part.soft_bin else "",
                            str(part.is_passing),
                            str(part.num_tests),
                            str(part.test_time_ms) if part.test_time_ms else "",
                            str(part.x_coord) if part.x_coord else "",
                            str(part.y_coord) if part.y_coord else "",
                            part.part_text or ""
                        ]
                        csv_lines.append(delimiter.join(row))

                elif export_type == "test_data":
                    # Export test results
                    if include_headers:
                        headers = [
                            "test_number", "test_name", "part_id", "site_id",
                            "result_value", "units", "low_limit", "high_limit",
                            "passing", "within_limits"
                        ]
                        csv_lines.append(delimiter.join(headers))

                    for part in stdf_data.part_results:
                        for test_result in part.test_results:
                            test_def = stdf_data.test_definitions.get(test_result.test_num)
                            row = [
                                str(test_result.test_num),
                                test_def.test_name if test_def else "",
                                test_result.part_id or "",
                                test_result.site_id,
                                str(test_result.result_value) if test_result.result_value else "",
                                test_result.units or "",
                                str(test_result.low_limit) if test_result.low_limit else "",
                                str(test_result.high_limit) if test_result.high_limit else "",
                                str(test_result.passing),
                                str(test_result.within_limits)
                            ]
                            csv_lines.append(delimiter.join(row))

                elif export_type == "bin_data":
                    # Export bin data
                    if include_headers:
                        headers = [
                            "bin_number", "bin_name", "bin_type", "part_count",
                            "is_pass_bin", "percentage"
                        ]
                        csv_lines.append(delimiter.join(headers))

                    total_parts = stdf_data.lot_summary.total_parts
                    for bin_num, bin_def in stdf_data.hard_bins.items():
                        percentage = (bin_def.part_count / total_parts * 100.0) if total_parts > 0 else 0.0
                        row = [
                            str(bin_def.bin_number),
                            bin_def.bin_name or "",
                            bin_def.bin_type,
                            str(bin_def.part_count),
                            str(bin_def.is_pass_bin),
                            f"{percentage:.2f}"
                        ]
                        csv_lines.append(delimiter.join(row))

                else:
                    return [TextContent(type="text", text=f"Error: Unsupported export type: {export_type}")]

                csv_content = "\n".join(csv_lines)

                result = {
                    "csv_data": csv_content,
                    "export_type": export_type,
                    "row_count": len(csv_lines) - (1 if include_headers else 0),
                    "exported_at": datetime.now().isoformat()
                }

                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]

            except Exception as e:
                return [TextContent(type="text", text=f"Error: {str(e)}")]

    def _setup_resources(self) -> None:
        """Setup MCP resources."""

        @self.server.list_resources()
        async def list_resources() -> List[Resource]:
            """List available STDF resources."""
            return [
                Resource(
                    uri="stdf://parser/config",
                    name="STDF Parser Configuration",
                    mimeType="application/json",
                    description="Current parser configuration settings"
                ),
                Resource(
                    uri="stdf://tools/list",
                    name="Available STDF Tools",
                    mimeType="application/json",
                    description="List of all available STDF analysis tools"
                )
            ]

        @self.server.read_resource()
        async def read_resource(uri: str) -> str:
            """Read STDF resource content."""
            if uri == "stdf://parser/config":
                config = {
                    "max_file_size_mb": self.parser.config.max_file_size_mb,
                    "enable_integrity_validation": self.parser.config.enable_integrity_validation,
                    "package_test_only": self.parser.config.package_test_only,
                    "streaming_buffer_size": self.parser.config.streaming_buffer_size
                }
                return json.dumps(config, indent=2)

            elif uri == "stdf://tools/list":
                tools = {
                    "metadata_tools": [
                        "validate_stdf_file",
                        "extract_metadata",
                        "extract_test_data",
                        "extract_bin_data",
                        "extract_site_data",
                        "extract_yield_data"
                    ],
                    "analysis_tools": [
                        "extract_filtered_data",
                        "calculate_statistics",
                        "generate_visualization",
                        "export_csv"
                    ],
                    "tool_count": 10
                }
                return json.dumps(tools, indent=2)

            else:
                raise ValueError(f"Unknown resource: {uri}")

    async def _load_stdf_file(self, file_path: str) -> STDFData:
        """Load and cache STDF file data."""
        # Check cache first
        if file_path in self._cached_stdf_data:
            return self._cached_stdf_data[file_path]

        # Load and parse file
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"STDF file not found: {file_path}")

        # Use converter to process file
        converter = STDFConverter(self.parser.config)
        stdf_data = converter.convert_file(path, validate_integrity=True)

        # Cache the result
        self._cached_stdf_data[file_path] = stdf_data

        return stdf_data

    async def run(self) -> None:
        """Run the STDF MCP server."""
        logger.info("Starting STDF-V4 MCP Server...")

        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="stdf-v4-server",
                    server_version="1.0.0",
                    capabilities={
                        "tools": {},
                        "resources": {}
                    }
                )
            )


def main() -> None:
    """Main entry point for STDF MCP server."""
    server = STDFMCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()