"""
Django app configuration for tenant_authx.
"""

from django.apps import AppConfig


class TenantAuthxConfig(AppConfig):
    """
    App configuration for django-tenant-authx.
    
    Provides tenant-aware authentication and authorization
    for multi-tenant SaaS applications.
    """
    
    name = "tenant_authx"
    verbose_name = "Tenant Authentication & Authorization"
    default_auto_field = "django.db.models.BigAutoField"
    
    def ready(self):
        """
        Called when Django starts. Used for signal registration
        and other initialization tasks.
        """
        # Import signals if needed in the future
        pass
