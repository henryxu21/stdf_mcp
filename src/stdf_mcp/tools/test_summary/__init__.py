"""Test parameter summary extraction module.

This module provides tools for extracting test parameter summaries by combining
TSR (Test Synopsis Record) statistics with PTR (Parametric Test Record) limits.
"""

from .parameter_summary import extract_test_parameter_summary

__all__ = ["extract_test_parameter_summary"]
