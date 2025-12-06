#!/bin/bash
# Virtual Environment Setup Script for STDF MCP Server
# Based on pyproject.toml specifications

set -e

echo "🔧 Setting up STDF MCP Server Virtual Environment"
echo "=================================================="

# Check Python version
echo "📋 Checking Python version..."
python3 --version
if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"; then
    echo "❌ Error: Python >= 3.11 required (pyproject.toml requirement)"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️ Upgrading pip..."
pip install --upgrade pip

# Install build dependencies
echo "🏗️ Installing build dependencies..."
pip install setuptools>=45 wheel

# Install main project dependencies from pyproject.toml
echo "📦 Installing main dependencies..."
pip install \
    "mcp>=1.0.0" \
    "numpy>=1.24.0" \
    "matplotlib>=3.6.0"

# Install development dependencies
echo "🔧 Installing development dependencies..."
pip install \
    "pytest>=7.0.0" \
    "pytest-cov>=4.0.0" \
    "pytest-asyncio>=0.21.0" \
    "black>=23.0.0" \
    "flake8>=6.0.0" \
    "mypy>=1.0.0" \
    "types-setuptools"

# Install project in editable mode
echo "📦 Installing STDF MCP Server in editable mode..."
pip install -e .

# Verify installation
echo "✅ Verifying installation..."
pip list | grep -E "(stdf-mcp|mcp|numpy|matplotlib|pytest|black|flake8|mypy)"

echo ""
echo "🎉 Virtual environment setup complete!"
echo ""
echo "To activate the environment:"
echo "  source venv/bin/activate"
echo ""
echo "To run the STDF MCP server:"
echo "  stdf-mcp"
echo ""
echo "To run tests:"
echo "  pytest"
echo ""
echo "To format code:"
echo "  black src/ tests/"
echo ""
echo "To check code quality:"
echo "  flake8 src/ tests/"
echo "  mypy src/"