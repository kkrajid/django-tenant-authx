"""
Authentication backends for django-tenant-authx.

Provides TenantAwareAuthBackend that extends Django's authentication
with tenant membership verification.
"""

from typing import Optional, TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.http import HttpRequest

from tenant_authx.utils import audit_log

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser
    from tenant_authx.models import Tenant


class TenantAwareAuthBackend(ModelBackend):
    """
    Authentication backend that verifies user credentials and tenant membership.
    
    This backend extends Django's ModelBackend to optionally verify
    that the user belongs to a specific tenant. When a tenant is
    provided in the authentication call, the user must have an
    active membership in that tenant to authenticate successfully.
    
    Usage:
        # Add to AUTHENTICATION_BACKENDS in settings.py
        AUTHENTICATION_BACKENDS = [
            'tenant_authx.backends.TenantAwareAuthBackend',
            'django.contrib.auth.backends.ModelBackend',  # Fallback
        ]
        
        # Authenticate with tenant verification
        user = authenticate(
            request,
            username='john',
            password='secret',
            tenant=tenant_instance
        )
    """
    
    def authenticate(
        self,
        request: Optional[HttpRequest] = None,
        username: str = None,
        password: str = None,
        tenant: "Tenant" = None,
        **kwargs
    ) -> Optional["AbstractUser"]:
        """
        Authenticate a user and optionally verify tenant membership.
        
        Args:
            request: The HTTP request (may be None)
            username: The username to authenticate
            password: The password to verify
            tenant: Optional tenant to verify membership in
            **kwargs: Additional arguments (e.g., email for email-based auth)
            
        Returns:
            The authenticated User instance if successful, None otherwise
        """
        # First, perform standard Django authentication
        User = get_user_model()
        
        # Support email-based authentication if username not provided
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        
        if username is None or password is None:
            return None
        
        try:
            user = User._default_manager.get_by_natural_key(username)
        except User.DoesNotExist:
            # Run the default password hasher to mitigate timing attacks
            User().set_password(password)
            audit_log(
                event="authentication_failed",
                request=request,
                success=False,
                extra={"reason": "user_not_found", "username": username},
            )
            return None
        
        # Check password
        if not user.check_password(password):
            audit_log(
                event="authentication_failed",
                user=user,
                tenant=tenant,
                request=request,
                success=False,
                extra={"reason": "invalid_password"},
            )
            return None
        
        # Check if user can authenticate (active, etc.)
        if not self.user_can_authenticate(user):
            audit_log(
                event="authentication_failed",
                user=user,
                tenant=tenant,
                request=request,
                success=False,
                extra={"reason": "user_inactive"},
            )
            return None
        
        # If tenant is specified, verify membership
        if tenant is not None:
            if not self._verify_tenant_membership(user, tenant, request):
                return None
        
        # Authentication successful
        audit_log(
            event="authentication_success",
            user=user,
            tenant=tenant,
            request=request,
            success=True,
        )
        
        return user
    
    def _verify_tenant_membership(
        self,
        user: "AbstractUser",
        tenant: "Tenant",
        request: Optional[HttpRequest] = None,
    ) -> bool:
        """
        Verify that a user has active membership in a tenant.
        
        Args:
            user: The user to verify
            tenant: The tenant to check membership in
            request: The HTTP request (for logging)
            
        Returns:
            True if user is a member, False otherwise
        """
        from tenant_authx.models import TenantMembership
        
        # Superusers can access any tenant
        if getattr(user, "is_superuser", False):
            return True
        
        # Check for active membership
        has_membership = TenantMembership.objects.filter(
            user=user,
            tenant=tenant,
            is_active=True,
        ).exists()
        
        if not has_membership:
            audit_log(
                event="authentication_failed",
                user=user,
                tenant=tenant,
                request=request,
                success=False,
                extra={"reason": "no_tenant_membership"},
            )
            return False
        
        # Also verify tenant is active
        if not tenant.is_active:
            audit_log(
                event="authentication_failed",
                user=user,
                tenant=tenant,
                request=request,
                success=False,
                extra={"reason": "tenant_inactive"},
            )
            return False
        
        return True
    
    def get_user(self, user_id):
        """
        Get a user by their primary key.
        
        Standard Django backend method required for session restoration.
        
        Args:
            user_id: The user's primary key
            
        Returns:
            User instance or None
        """
        User = get_user_model()
        try:
            user = User._default_manager.get(pk=user_id)
        except User.DoesNotExist:
            return None
        
        return user if self.user_can_authenticate(user) else None
    
    def has_perm(
        self,
        user_obj: "AbstractUser",
        perm: str,
        obj=None
    ) -> bool:
        """
        Check if a user has a specific permission.
        
        This method integrates with Django's permission checking.
        For tenant-scoped permissions, use TenantUser.has_perm() instead.
        
        Args:
            user_obj: The user to check
            perm: The permission string
            obj: Optional object for object-level permissions
            
        Returns:
            True if user has the permission
        """
        # For tenant-scoped permissions, this falls through to the
        # regular Django permission check. Use TenantUser for proper
        # tenant-scoped permission checking.
        return super().has_perm(user_obj, perm, obj)
