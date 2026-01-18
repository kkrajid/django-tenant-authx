"""
Default handlers for tenant_authx events.

Provides default implementations for handling tenant resolution
failures and other configurable callbacks.
"""

from django.http import Http404, HttpRequest, HttpResponse

from tenant_authx.exceptions import TenantNotFoundError


def default_tenant_not_found(
    request: HttpRequest, 
    exception: TenantNotFoundError
) -> HttpResponse:
    """
    Default handler for tenant resolution failures.
    
    Returns a 404 response. Override this in settings by setting
    TENANT_AUTHX_TENANT_NOT_FOUND_HANDLER to your custom handler.
    
    Args:
        request: The HTTP request that failed tenant resolution
        exception: The TenantNotFoundError that was raised
        
    Returns:
        HTTP 404 response
        
    Raises:
        Http404: If the view should show Django's 404 page
    """
    raise Http404(f"Tenant not found: {exception.identifier or 'unknown'}")


def return_none_on_tenant_not_found(
    request: HttpRequest,
    exception: TenantNotFoundError
) -> None:
    """
    Alternative handler that returns None instead of raising an error.
    
    This allows the request to proceed without a tenant context,
    which may be useful for public pages or landing pages.
    
    Args:
        request: The HTTP request
        exception: The TenantNotFoundError that was raised
        
    Returns:
        None (request.tenant will be None)
    """
    return None
