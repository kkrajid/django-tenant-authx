"""
Utility functions for django-tenant-authx.

Provides helper functions for common operations like tenant context
validation, permission format validation, and audit logging.
"""

import logging
import re
from typing import Optional, TYPE_CHECKING

from django.utils import timezone

from tenant_authx.conf import tenant_authx_settings
from tenant_authx.exceptions import (
    InvalidTenantContextError,
    InvalidPermissionFormat,
)

if TYPE_CHECKING:
    from tenant_authx.models import Tenant


# Permission codename pattern: app_label.action_model
# Examples: orders.view_order, billing.add_invoice
PERMISSION_CODENAME_PATTERN = re.compile(
    r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$"
)


def validate_tenant_context(tenant: Optional["Tenant"]) -> "Tenant":
    """
    Validate that a tenant context exists and is valid.
    
    Args:
        tenant: The tenant to validate
        
    Returns:
        The validated tenant
        
    Raises:
        InvalidTenantContextError: If tenant is None or invalid
    """
    if tenant is None:
        raise InvalidTenantContextError(
            "Tenant context is required but not available"
        )
    
    if not tenant.is_active:
        raise InvalidTenantContextError(
            f"Tenant '{tenant.slug}' is inactive"
        )
    
    return tenant


def is_valid_tenant_context(tenant: Optional["Tenant"]) -> bool:
    """
    Check if a tenant context is valid without raising exceptions.
    
    Args:
        tenant: The tenant to validate
        
    Returns:
        True if tenant is valid and active, False otherwise
    """
    if tenant is None:
        return False
    
    if not getattr(tenant, 'is_active', False):
        return False
    
    return True


def validate_permission_codename(codename: str) -> str:
    """
    Validate that a permission codename follows Django conventions.
    
    Valid format: 'app_label.action_model' (all lowercase, underscores allowed)
    Examples: 'orders.view_order', 'billing.add_invoice'
    
    Args:
        codename: The permission codename to validate
        
    Returns:
        The validated codename
        
    Raises:
        InvalidPermissionFormat: If codename doesn't match expected format
    """
    if not codename or not isinstance(codename, str):
        raise InvalidPermissionFormat(
            "Permission codename must be a non-empty string",
            codename=str(codename)
        )
    
    if not PERMISSION_CODENAME_PATTERN.match(codename):
        raise InvalidPermissionFormat(codename=codename)
    
    return codename


def is_valid_permission_codename(codename: str) -> bool:
    """
    Check if a permission codename is valid without raising exceptions.
    
    Args:
        codename: The permission codename to validate
        
    Returns:
        True if codename is valid, False otherwise
    """
    if not codename or not isinstance(codename, str):
        return False
    
    return bool(PERMISSION_CODENAME_PATTERN.match(codename))


def get_audit_logger() -> logging.Logger:
    """
    Get the audit logger instance.
    
    Returns:
        Logger instance for audit events
    """
    return logging.getLogger(tenant_authx_settings.AUDIT_LOGGER)


def audit_log(
    event: str,
    user=None,
    tenant=None,
    permission: str = None,
    success: bool = True,
    request=None,
    extra: dict = None,
):
    """
    Log an audit event for authentication/authorization activities.
    
    Args:
        event: Event type (e.g., 'authentication', 'permission_check')
        user: The user involved (if any)
        tenant: The tenant context (if any)
        permission: The permission being checked (if any)
        success: Whether the operation succeeded
        request: The HTTP request (for IP/user agent extraction)
        extra: Additional context data
    """
    if not tenant_authx_settings.AUDIT_ENABLED:
        return
    
    logger = get_audit_logger()
    
    # Build log data
    log_data = {
        "event": event,
        "timestamp": timezone.now().isoformat(),
        "success": success,
    }
    
    if user:
        log_data["user_id"] = getattr(user, "pk", None)
        log_data["username"] = getattr(user, "username", str(user))
        log_data["is_superuser"] = getattr(user, "is_superuser", False)
    
    if tenant:
        log_data["tenant_id"] = str(getattr(tenant, "pk", None))
        log_data["tenant_slug"] = getattr(tenant, "slug", str(tenant))
    
    if permission:
        log_data["permission"] = permission
    
    if request:
        log_data["ip_address"] = get_client_ip(request)
        log_data["user_agent"] = request.META.get("HTTP_USER_AGENT", "")[:200]
        log_data["path"] = request.path
        log_data["method"] = request.method
    
    if extra:
        log_data.update(extra)
    
    # Log at appropriate level
    if success:
        logger.info(f"Audit: {event}", extra={"audit_data": log_data})
    else:
        logger.warning(f"Audit: {event} FAILED", extra={"audit_data": log_data})


def get_client_ip(request) -> str:
    """
    Extract client IP address from request.
    
    Handles proxied requests via X-Forwarded-For header.
    
    Args:
        request: Django HTTP request
        
    Returns:
        Client IP address string
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        # Take the first IP in the chain (client IP)
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def get_tenant_model():
    """
    Get the configured Tenant model class.
    
    Returns:
        The Tenant model class
    """
    from django.apps import apps
    
    model_path = tenant_authx_settings.TENANT_MODEL
    app_label, model_name = model_path.rsplit(".", 1)
    return apps.get_model(app_label, model_name)


def normalize_permission_list(perms) -> list:
    """
    Normalize a permission argument to a list.
    
    Args:
        perms: A single permission string or iterable of permissions
        
    Returns:
        List of permission strings
    """
    if isinstance(perms, str):
        return [perms]
    return list(perms)
