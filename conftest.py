"""
Pytest configuration for tenant_authx tests.

This conftest.py file ensures Django settings are properly configured
and the Python path is set up correctly for testing.
"""

import os
import sys

import django
from django.conf import settings

# Add project root to Python path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def pytest_configure(config):
    """Configure Django settings for pytest."""
    if not settings.configured:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")
        django.setup()
