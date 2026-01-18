"""
Middleware for django-tenant-authx.

Provides TenantResolutionMiddleware for resolving tenants from requests
and TenantUserMiddleware for creating the TenantUser abstraction.
"""

import re
from typing import Callable, Optional

from django.http import HttpRequest, HttpResponse
from django.utils.module_loading import import_string

from tenant_authx.conf import tenant_authx_settings
from tenant_authx.exceptions import TenantNotFoundError, TenantInactiveError
from tenant_authx.resolvers import get_resolver
from tenant_authx.utils import audit_log


class TenantResolutionMiddleware:
    """
    Middleware that resolves the current tenant from each request.
    
    This middleware must run after AuthenticationMiddleware to ensure
    the user is available for audit logging. The resolved tenant is
    attached to request.tenant.
    
    Configuration:
        TENANT_AUTHX_TENANT_RESOLUTION_STRATEGY: 'domain', 'subdomain', 'path', or 'header'
        TENANT_AUTHX_TENANT_NOT_FOUND_HANDLER: Handler for resolution failures
        TENANT_AUTHX_TENANT_EXEMPT_URLS: List of URL patterns to skip
    """
    
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        """
        Initialize the middleware.
        
        Args:
            get_response: The next middleware/view in the chain
        """
        self.get_response = get_response
        self._resolver = None
        self._exempt_patterns = self._compile_exempt_patterns()
    
    @property
    def resolver(self):
        """Lazy-load the resolver to avoid errors during startup."""
        if self._resolver is None:
            self._resolver = get_resolver()
        return self._resolver
    
    def _compile_exempt_patterns(self) -> list:
        """Compile exempt URL patterns for faster matching."""
        patterns = tenant_authx_settings.TENANT_EXEMPT_URLS
        return [re.compile(pattern) for pattern in patterns]
    
    def _is_exempt(self, path: str) -> bool:
        """Check if a path is exempt from tenant resolution."""
        return any(pattern.match(path) for pattern in self._exempt_patterns)
    
    def _get_handler(self):
        """Get the configured not-found handler."""
        handler_path = tenant_authx_settings.TENANT_NOT_FOUND_HANDLER
        
        if handler_path == "raise":
            return None  # Will re-raise the exception
        elif handler_path == "none":
            return lambda req, exc: None
        else:
            return import_string(handler_path)
    
    def __call__(self, request: HttpRequest) -> HttpResponse:
        """
        Process the request and resolve tenant.
        
        Args:
            request: The incoming HTTP request
            
        Returns:
            The response from the view/next middleware
        """
        # Initialize tenant as None
        request.tenant = None
        
        # Skip tenant resolution for exempt URLs
        if self._is_exempt(request.path):
            return self.get_response(request)
        
        try:
            request.tenant = self.resolver.resolve(request)
            
            # Log successful resolution
            audit_log(
                event="tenant_resolved",
                tenant=request.tenant,
                user=getattr(request, "user", None),
                request=request,
                success=True,
            )
            
        except (TenantNotFoundError, TenantInactiveError) as e:
            # Log failed resolution
            audit_log(
                event="tenant_resolution_failed",
                user=getattr(request, "user", None),
                request=request,
                success=False,
                extra={"error": str(e), "identifier": getattr(e, "identifier", None)},
            )
            
            # Call the configured handler
            handler = self._get_handler()
            
            if handler is None:
                raise  # Re-raise the exception
            
            result = handler(request, e)
            
            # Handler can return a response directly
            if isinstance(result, HttpResponse):
                return result
            
            # Or set request.tenant to None (or another value)
            request.tenant = result
        
        return self.get_response(request)


class TenantUserMiddleware:
    """
    Middleware that creates the request.tenant_user abstraction.
    
    This middleware combines request.user and request.tenant into
    a TenantUser instance that provides tenant-scoped permission
    checking and other utilities.
    
    This middleware must run after both AuthenticationMiddleware
    and TenantResolutionMiddleware.
    """
    
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        """
        Initialize the middleware.
        
        Args:
            get_response: The next middleware/view in the chain
        """
        self.get_response = get_response
    
    def __call__(self, request: HttpRequest) -> HttpResponse:
        """
        Process the request and create TenantUser.
        
        Args:
            request: The incoming HTTP request
            
        Returns:
            The response from the view/next middleware
        """
        from tenant_authx.permissions import TenantUser
        
        # Initialize tenant_user as None
        request.tenant_user = None
        
        # Only create TenantUser if we have both user and tenant
        user = getattr(request, "user", None)
        tenant = getattr(request, "tenant", None)
        
        if user and tenant and user.is_authenticated:
            request.tenant_user = TenantUser(user=user, tenant=tenant)
        
        return self.get_response(request)
