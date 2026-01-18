"""
DRF authentication classes for django-tenant-authx.

Provides authentication classes that verify both user credentials
and tenant membership for REST API requests.
"""

from typing import Optional, Tuple, TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from rest_framework import exceptions
from rest_framework.authentication import (
    BaseAuthentication,
    SessionAuthentication,
    TokenAuthentication,
)
from rest_framework.request import Request

from tenant_authx.permissions import TenantUser
from tenant_authx.utils import audit_log

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser
    from tenant_authx.models import Tenant


class TenantAuthenticationMixin:
    """
    Mixin providing tenant membership verification for DRF authentication classes.
    
    This mixin adds tenant-aware authentication by:
    1. Performing the base authentication
    2. Verifying the user is a member of request.tenant
    3. Creating and attaching TenantUser to the request
    """
    
    def verify_tenant_membership(
        self,
        request: Request,
        user: "AbstractUser",
    ) -> "TenantUser":
        """
        Verify user is a member of the request's tenant.
        
        Args:
            request: The DRF request
            user: The authenticated user
            
        Returns:
            TenantUser instance
            
        Raises:
            AuthenticationFailed: If user is not a tenant member
        """
        from tenant_authx.models import TenantMembership
        
        tenant = getattr(request, "tenant", None)
        
        if tenant is None:
            # No tenant context - allow if settings permit
            return None
        
        # Superusers bypass membership check
        if getattr(user, "is_superuser", False):
            return TenantUser(user=user, tenant=tenant)
        
        # Check for active membership
        try:
            membership = TenantMembership.objects.select_related(
                "tenant"
            ).prefetch_related(
                "roles__permissions"
            ).get(
                user=user,
                tenant=tenant,
                is_active=True,
            )
        except TenantMembership.DoesNotExist:
            audit_log(
                event="api_authentication_failed",
                user=user,
                tenant=tenant,
                success=False,
                extra={"reason": "no_tenant_membership"},
            )
            raise exceptions.AuthenticationFailed(
                _("You are not a member of this tenant.")
            )
        
        return TenantUser(user=user, tenant=tenant)


class TenantSessionAuthentication(TenantAuthenticationMixin, SessionAuthentication):
    """
    Session-based authentication with tenant membership verification.
    
    This extends DRF's SessionAuthentication to verify that the
    authenticated user is a member of the current tenant.
    
    Usage:
        REST_FRAMEWORK = {
            'DEFAULT_AUTHENTICATION_CLASSES': [
                'tenant_authx.drf.TenantSessionAuthentication',
            ]
        }
    """
    
    def authenticate(
        self,
        request: Request
    ) -> Optional[Tuple["AbstractUser", None]]:
        """
        Authenticate using session and verify tenant membership.
        
        Args:
            request: The DRF request
            
        Returns:
            Tuple of (user, None) or None
            
        Raises:
            AuthenticationFailed: If session auth fails or user not in tenant
        """
        # Perform session authentication
        result = super().authenticate(request)
        
        if result is None:
            return None
        
        user, auth = result
        
        # Verify tenant membership and create TenantUser
        tenant_user = self.verify_tenant_membership(request, user)
        if tenant_user:
            # Attach TenantUser to request for later use
            request.tenant_user = tenant_user
        
        audit_log(
            event="api_authentication_success",
            user=user,
            tenant=getattr(request, "tenant", None),
            success=True,
            extra={"method": "session"},
        )
        
        return result


class TenantTokenAuthentication(TenantAuthenticationMixin, TokenAuthentication):
    """
    Token-based authentication with tenant membership verification.
    
    This extends DRF's TokenAuthentication to verify that the
    authenticated user is a member of the current tenant.
    
    Usage:
        REST_FRAMEWORK = {
            'DEFAULT_AUTHENTICATION_CLASSES': [
                'tenant_authx.drf.TenantTokenAuthentication',
            ]
        }
    """
    
    def authenticate(
        self,
        request: Request
    ) -> Optional[Tuple["AbstractUser", str]]:
        """
        Authenticate using token and verify tenant membership.
        
        Args:
            request: The DRF request
            
        Returns:
            Tuple of (user, token) or None
            
        Raises:
            AuthenticationFailed: If token auth fails or user not in tenant
        """
        # Perform token authentication
        result = super().authenticate(request)
        
        if result is None:
            return None
        
        user, token = result
        
        # Verify tenant membership and create TenantUser
        tenant_user = self.verify_tenant_membership(request, user)
        if tenant_user:
            # Attach TenantUser to request for later use
            request.tenant_user = tenant_user
        
        audit_log(
            event="api_authentication_success",
            user=user,
            tenant=getattr(request, "tenant", None),
            success=True,
            extra={"method": "token"},
        )
        
        return result


class TenantBasicAuthentication(TenantAuthenticationMixin, BaseAuthentication):
    """
    Basic HTTP authentication with tenant membership verification.
    
    This provides HTTP Basic authentication with tenant awareness.
    Note: Basic auth should only be used over HTTPS.
    
    Usage:
        REST_FRAMEWORK = {
            'DEFAULT_AUTHENTICATION_CLASSES': [
                'tenant_authx.drf.TenantBasicAuthentication',
            ]
        }
    """
    
    www_authenticate_realm = "api"
    
    def authenticate(
        self,
        request: Request
    ) -> Optional[Tuple["AbstractUser", None]]:
        """
        Authenticate using HTTP Basic Auth and verify tenant membership.
        
        Args:
            request: The DRF request
            
        Returns:
            Tuple of (user, None) or None
        """
        import base64
        import binascii
        
        from django.contrib.auth import authenticate
        
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        
        if not auth_header.startswith("Basic "):
            return None
        
        try:
            auth_decoded = base64.b64decode(
                auth_header[6:]
            ).decode("utf-8")
            username, password = auth_decoded.split(":", 1)
        except (ValueError, UnicodeDecodeError, binascii.Error):
            raise exceptions.AuthenticationFailed(_("Invalid basic auth header."))
        
        # Authenticate credentials
        user = authenticate(request=request, username=username, password=password)
        
        if user is None:
            raise exceptions.AuthenticationFailed(_("Invalid username/password."))
        
        # Verify tenant membership
        tenant_user = self.verify_tenant_membership(request, user)
        if tenant_user:
            request.tenant_user = tenant_user
        
        audit_log(
            event="api_authentication_success",
            user=user,
            tenant=getattr(request, "tenant", None),
            success=True,
            extra={"method": "basic"},
        )
        
        return (user, None)
    
    def authenticate_header(self, request: Request) -> str:
        """
        Return the WWW-Authenticate header value.
        """
        return f'Basic realm="{self.www_authenticate_realm}"'
