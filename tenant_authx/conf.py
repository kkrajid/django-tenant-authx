"""
Configuration settings for django-tenant-authx.

Provides default settings and a Settings accessor class that
allows per-project customization via Django settings.
"""

from django.conf import settings


# Default configuration values
TENANT_AUTHX_DEFAULTS = {
    # Tenant resolution strategy: 'domain', 'subdomain', 'path'
    "TENANT_RESOLUTION_STRATEGY": "domain",
    
    # URL path pattern for path-based resolution (regex with named group 'tenant_slug')
    "TENANT_PATH_PATTERN": r"^/(?P<tenant_slug>[\w-]+)/",
    
    # Header name for header-based tenant resolution (optional)
    "TENANT_HEADER_NAME": "X-Tenant-Slug",
    
    # Behavior when tenant resolution fails
    # Options: 'raise', 'none', or path to custom handler function
    "TENANT_NOT_FOUND_HANDLER": "tenant_authx.handlers.default_tenant_not_found",
    
    # Cache timeout for permission checks (seconds), 0 to disable
    "PERMISSION_CACHE_TIMEOUT": 300,
    
    # Allow superusers to bypass tenant checks
    "SUPERUSER_BYPASS": True,
    
    # Enable audit logging for auth events
    "AUDIT_ENABLED": True,
    
    # Audit logger name
    "AUDIT_LOGGER": "tenant_authx.audit",
    
    # Custom tenant model (if extending the default)
    "TENANT_MODEL": "tenant_authx.Tenant",
    
    # URLs that should bypass tenant resolution (list of regex patterns)
    "TENANT_EXEMPT_URLS": [],
    
    # Public tenant slug (for public/shared content)
    "PUBLIC_TENANT_SLUG": None,
    
    # Base domain for subdomain extraction (e.g., 'example.com')
    "BASE_DOMAIN": None,
}


class Settings:
    """
    Settings accessor that reads from Django settings with fallback to defaults.
    
    Usage:
        from tenant_authx.conf import tenant_authx_settings
        strategy = tenant_authx_settings.TENANT_RESOLUTION_STRATEGY
    """
    
    def __getattr__(self, name: str):
        """
        Get a setting value.
        
        First checks Django settings for TENANT_AUTHX_{name},
        then falls back to default value.
        
        Args:
            name: Setting name (without TENANT_AUTHX_ prefix)
            
        Returns:
            The setting value
            
        Raises:
            AttributeError: If setting name is not valid
        """
        if name not in TENANT_AUTHX_DEFAULTS:
            raise AttributeError(f"Invalid tenant_authx setting: '{name}'")
        
        # Look for setting in Django settings with TENANT_AUTHX_ prefix
        django_setting_name = f"TENANT_AUTHX_{name}"
        return getattr(
            settings,
            django_setting_name,
            TENANT_AUTHX_DEFAULTS[name]
        )
    
    def __dir__(self):
        """Return list of available settings."""
        return list(TENANT_AUTHX_DEFAULTS.keys())


# Singleton instance for easy access
tenant_authx_settings = Settings()
