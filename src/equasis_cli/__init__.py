#!/usr/bin/env python3
"""
Equasis CLI Tool - A command-line interface for accessing Equasis maritime data

This package provides programmatic access to vessel and fleet information
from the Equasis database through a clean, scriptable CLI interface.
"""

from .main import main
from .client import EquasisClient, SimpleVesselInfo, FleetInfo
from .parser import EquasisParser, EquasisVesselData, VesselBasicInfo
from .formatter import OutputFormatter
from .banner import get_version, display_banner, check_credentials, display_credentials_note
from .interactive import InteractiveShell

from ._version import __version__
__author__ = "rhinonix"
__email__ = "rhinonix.github.exclaim769@slmail.me"

# Public API
__all__ = [
    'main',
    'EquasisClient',
    'EquasisParser',
    'EquasisVesselData',
    'VesselBasicInfo',
    'SimpleVesselInfo',
    'FleetInfo',
    'OutputFormatter',
    'get_version',
    'display_banner',
    'check_credentials',
    'display_credentials_note',
    'InteractiveShell'
]
