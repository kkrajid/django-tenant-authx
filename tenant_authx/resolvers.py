"""
Tenant resolution strategies for django-tenant-authx.

Provides different strategies for resolving the current tenant
from incoming HTTP requests: domain, subdomain, and URL path.
"""

import re
from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

from django.http import HttpRequest

from tenant_authx.conf import tenant_authx_settings
from tenant_authx.exceptions import TenantNotFoundError, TenantInactiveError

if TYPE_CHECKING:
    from tenant_authx.models import Tenant


class BaseTenantResolver(ABC):
    """
    Abstract base class for tenant resolution strategies.
    
    Subclasses must implement the resolve() method to extract
    tenant identification from the request and return the
    corresponding Tenant instance.
    """
    
    @abstractmethod
    def resolve(self, request: HttpRequest) -> Optional["Tenant"]:
        """
        Resolve the tenant from the request.
        
        Args:
            request: The incoming HTTP request
            
        Returns:
            The resolved Tenant instance, or None if not found
            
        Raises:
            TenantNotFoundError: If tenant identification is present but invalid
            TenantInactiveError: If the resolved tenant is inactive
        """
        pass
    
    def get_tenant_by_slug(self, slug: str) -> "Tenant":
        """
        Get a tenant by its slug.
        
        Args:
            slug: The tenant slug to look up
            
        Returns:
            The Tenant instance
            
        Raises:
            TenantNotFoundError: If no tenant with that slug exists
            TenantInactiveError: If the tenant is inactive
        """
        from tenant_authx.models import Tenant
        
        try:
            tenant = Tenant.objects.get(slug=slug.lower())
        except Tenant.DoesNotExist:
            raise TenantNotFoundError(identifier=slug)
        
        if not tenant.is_active:
            raise TenantInactiveError(
                f"Tenant '{slug}' is inactive",
                tenant=tenant
            )
        
        return tenant
    
    def get_tenant_by_domain(self, domain: str) -> "Tenant":
        """
        Get a tenant by its domain.
        
        Args:
            domain: The domain to look up
            
        Returns:
            The Tenant instance
            
        Raises:
            TenantNotFoundError: If no tenant with that domain exists
            TenantInactiveError: If the tenant is inactive
        """
        from tenant_authx.models import Tenant
        
        try:
            tenant = Tenant.objects.get(domain=domain.lower())
        except Tenant.DoesNotExist:
            raise TenantNotFoundError(identifier=domain)
        
        if not tenant.is_active:
            raise TenantInactiveError(
                f"Tenant with domain '{domain}' is inactive",
                tenant=tenant
            )
        
        return tenant


class DomainTenantResolver(BaseTenantResolver):
    """
    Resolves tenant by matching the request host against Tenant.domain.
    
    This is useful when each tenant has its own custom domain
    (e.g., tenant1.com, tenant2.com).
    """
    
    def resolve(self, request: HttpRequest) -> Optional["Tenant"]:
        """
        Resolve tenant by domain.
        
        Args:
            request: The incoming HTTP request
            
        Returns:
            The resolved Tenant instance
            
        Raises:
            TenantNotFoundError: If no tenant matches the domain
        """
        host = request.get_host()
        
        # Remove port if present
        if ":" in host:
            host = host.split(":")[0]
        
        return self.get_tenant_by_domain(host)


class SubdomainTenantResolver(BaseTenantResolver):
    """
    Resolves tenant by extracting subdomain and matching against Tenant.slug.
    
    This is useful when tenants are accessed via subdomains
    (e.g., tenant1.example.com, tenant2.example.com).
    
    Requires BASE_DOMAIN to be configured in settings.
    """
    
    def __init__(self):
        self.base_domain = tenant_authx_settings.BASE_DOMAIN
        if not self.base_domain:
            raise ValueError(
                "TENANT_AUTHX_BASE_DOMAIN must be set for subdomain resolution"
            )
    
    def resolve(self, request: HttpRequest) -> Optional["Tenant"]:
        """
        Resolve tenant by subdomain.
        
        Args:
            request: The incoming HTTP request
            
        Returns:
            The resolved Tenant instance
            
        Raises:
            TenantNotFoundError: If subdomain doesn't match any tenant
        """
        host = request.get_host()
        
        # Remove port if present
        if ":" in host:
            host = host.split(":")[0]
        
        # Extract subdomain
        subdomain = self._extract_subdomain(host)
        
        if not subdomain:
            raise TenantNotFoundError(
                message="No subdomain found in request",
                identifier=host
            )
        
        return self.get_tenant_by_slug(subdomain)
    
    def _extract_subdomain(self, host: str) -> Optional[str]:
        """
        Extract the subdomain from a host.
        
        Args:
            host: The full host (e.g., 'tenant.example.com')
            
        Returns:
            The subdomain, or None if no subdomain
        """
        base = self.base_domain.lower()
        host = host.lower()
        
        if not host.endswith(f".{base}"):
            return None
        
        # Remove the base domain to get the subdomain
        subdomain = host[: -(len(base) + 1)]  # +1 for the dot
        
        # Handle nested subdomains (take the first part)
        if "." in subdomain:
            subdomain = subdomain.split(".")[0]
        
        return subdomain if subdomain else None


class PathTenantResolver(BaseTenantResolver):
    """
    Resolves tenant by extracting slug from the URL path.
    
    This is useful when tenants are accessed via URL paths
    (e.g., /tenant1/dashboard, /tenant2/dashboard).
    
    The path pattern is configured via TENANT_PATH_PATTERN setting.
    """
    
    def __init__(self):
        pattern = tenant_authx_settings.TENANT_PATH_PATTERN
        self.pattern = re.compile(pattern)
    
    def resolve(self, request: HttpRequest) -> Optional["Tenant"]:
        """
        Resolve tenant from URL path.
        
        Args:
            request: The incoming HTTP request
            
        Returns:
            The resolved Tenant instance
            
        Raises:
            TenantNotFoundError: If path doesn't contain valid tenant slug
        """
        path = request.path
        match = self.pattern.match(path)
        
        if not match:
            raise TenantNotFoundError(
                message="No tenant slug found in URL path",
                identifier=path
            )
        
        try:
            slug = match.group("tenant_slug")
        except IndexError:
            raise TenantNotFoundError(
                message="Tenant slug pattern matched but 'tenant_slug' group not found",
                identifier=path
            )
        
        return self.get_tenant_by_slug(slug)


class HeaderTenantResolver(BaseTenantResolver):
    """
    Resolves tenant from a custom HTTP header.
    
    This is useful for API-first applications where the tenant
    is specified via a header (e.g., X-Tenant-Slug: tenant1).
    
    The header name is configured via TENANT_HEADER_NAME setting.
    """
    
    def __init__(self):
        header_name = tenant_authx_settings.TENANT_HEADER_NAME
        # Convert to Django's META key format
        self.header_key = f"HTTP_{header_name.upper().replace('-', '_')}"
    
    def resolve(self, request: HttpRequest) -> Optional["Tenant"]:
        """
        Resolve tenant from HTTP header.
        
        Args:
            request: The incoming HTTP request
            
        Returns:
            The resolved Tenant instance
            
        Raises:
            TenantNotFoundError: If header not present or invalid
        """
        slug = request.META.get(self.header_key)
        
        if not slug:
            raise TenantNotFoundError(
                message=f"Tenant header '{tenant_authx_settings.TENANT_HEADER_NAME}' not found",
                identifier=None
            )
        
        return self.get_tenant_by_slug(slug)


# Registry of available resolvers
RESOLVER_REGISTRY = {
    "domain": DomainTenantResolver,
    "subdomain": SubdomainTenantResolver,
    "path": PathTenantResolver,
    "header": HeaderTenantResolver,
}


def get_resolver(strategy: str = None) -> BaseTenantResolver:
    """
    Get the appropriate tenant resolver for the configured strategy.
    
    Args:
        strategy: Override the configured strategy (optional)
        
    Returns:
        An instance of the appropriate resolver
        
    Raises:
        ValueError: If the strategy is not recognized
    """
    if strategy is None:
        strategy = tenant_authx_settings.TENANT_RESOLUTION_STRATEGY
    
    strategy = strategy.lower()
    
    if strategy not in RESOLVER_REGISTRY:
        raise ValueError(
            f"Unknown tenant resolution strategy: '{strategy}'. "
            f"Available strategies: {list(RESOLVER_REGISTRY.keys())}"
        )
    
    return RESOLVER_REGISTRY[strategy]()
