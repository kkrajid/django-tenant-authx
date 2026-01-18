"""
Custom exception classes for django-tenant-authx.

These exceptions provide clear error handling for tenant-related
authentication and authorization failures.
"""


class TenantAuthException(Exception):
    """
    Base exception for all tenant auth errors.
    
    All custom exceptions in this library inherit from this class,
    allowing catch-all handling when needed.
    """
    
    def __init__(self, message: str = None, tenant=None, user=None):
        """
        Initialize the exception.
        
        Args:
            message: Human-readable error message
            tenant: The tenant context (if available)
            user: The user context (if available)
        """
        self.message = message or self.__class__.__doc__
        self.tenant = tenant
        self.user = user
        super().__init__(self.message)


class TenantNotFoundError(TenantAuthException):
    """
    Raised when a tenant cannot be resolved from the request.
    
    This typically occurs when:
    - The domain/subdomain doesn't match any tenant
    - The URL path doesn't contain a valid tenant slug
    - The requested tenant doesn't exist in the database
    """
    
    def __init__(self, message: str = None, identifier: str = None, **kwargs):
        """
        Initialize the exception.
        
        Args:
            message: Human-readable error message
            identifier: The tenant identifier that was not found
        """
        self.identifier = identifier
        if message is None and identifier:
            message = f"Tenant not found: '{identifier}'"
        super().__init__(message, **kwargs)


class TenantInactiveError(TenantAuthException):
    """
    Raised when attempting to access an inactive tenant.
    
    Tenants can be deactivated for various reasons (billing, suspension, etc.)
    and should not be accessible when inactive.
    """
    pass


class TenantMembershipError(TenantAuthException):
    """
    Raised when a user lacks required tenant membership.
    
    This occurs when:
    - User tries to access a tenant they don't belong to
    - User's membership in the tenant is inactive
    - User tries to authenticate without tenant membership
    """
    
    def __init__(self, message: str = None, **kwargs):
        if message is None:
            message = "User is not a member of this tenant"
        super().__init__(message, **kwargs)


class TenantPermissionError(TenantAuthException):
    """
    Raised when a permission check fails within a tenant context.
    
    This is used when a user is a member of a tenant but lacks
    the specific permission required for an operation.
    """
    
    def __init__(
        self, 
        message: str = None, 
        permission: str = None,
        **kwargs
    ):
        """
        Initialize the exception.
        
        Args:
            message: Human-readable error message
            permission: The permission that was denied
        """
        self.permission = permission
        if message is None and permission:
            message = f"Permission denied: '{permission}'"
        super().__init__(message, **kwargs)


class InvalidTenantContextError(TenantAuthException):
    """
    Raised when an operation requires a tenant context but none is available.
    
    This typically indicates a middleware configuration issue or
    an attempt to check permissions outside of a request context.
    """
    
    def __init__(self, message: str = None, **kwargs):
        if message is None:
            message = "No valid tenant context available"
        super().__init__(message, **kwargs)


class InvalidPermissionFormat(TenantAuthException):
    """
    Raised when a permission codename doesn't follow Django conventions.
    
    Permissions should follow the format: 'app_label.action_model'
    (e.g., 'orders.view_order', 'billing.edit_invoice')
    """
    
    def __init__(self, message: str = None, codename: str = None, **kwargs):
        """
        Initialize the exception.
        
        Args:
            message: Human-readable error message
            codename: The invalid permission codename
        """
        self.codename = codename
        if message is None and codename:
            message = (
                f"Invalid permission format: '{codename}'. "
                "Expected format: 'app_label.action_model'"
            )
        super().__init__(message, **kwargs)
