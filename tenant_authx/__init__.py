"""
django-tenant-authx

A Django library providing tenant-aware authentication and authorization
for multi-tenant SaaS applications.
"""

__version__ = "0.1.0"
__author__ = "RAJID K K"
__email__ = "rajidkk34@gmail.com"

# Public API exports
from tenant_authx.permissions import TenantUser, PermissionChecker
from tenant_authx.exceptions import (
    TenantAuthException,
    TenantNotFoundError,
    TenantMembershipError,
    TenantPermissionError,
)
from tenant_authx.utils import (
    is_valid_tenant_context,
    is_valid_permission_codename,
)

__all__ = [
    "__version__",
    "TenantUser",
    "PermissionChecker",
    "TenantAuthException",
    "TenantNotFoundError",
    "TenantMembershipError",
    "TenantPermissionError",
    "is_valid_tenant_context",
    "is_valid_permission_codename",
]
