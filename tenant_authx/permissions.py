"""
Permission system for django-tenant-authx.

Provides the TenantUser abstraction and PermissionChecker engine
for tenant-scoped authorization.
"""

from typing import Optional, Set, TYPE_CHECKING

from tenant_authx.conf import tenant_authx_settings
from tenant_authx.utils import audit_log, validate_tenant_context

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser
    from tenant_authx.models import Tenant, TenantMembership


class TenantUser:
    """
    Represents a user's identity within a specific tenant context.
    
    This class combines a User and Tenant to provide unified
    access to tenant-scoped permissions and membership information.
    Permission checks are cached per-instance for performance.
    
    Attributes:
        user: The Django user instance
        tenant: The tenant context
        is_authenticated: Whether the user is authenticated
        is_superuser: Whether the user is a superuser
    """
    
    def __init__(self, user: "AbstractUser", tenant: "Tenant"):
        """
        Initialize the TenantUser.
        
        Args:
            user: The Django user instance
            tenant: The tenant context
        """
        self.user = user
        self.tenant = tenant
        self._permission_cache: Optional[Set[str]] = None
        self._membership_cache: Optional["TenantMembership"] = None
        self._is_member_cache: Optional[bool] = None
    
    @property
    def is_authenticated(self) -> bool:
        """Check if the user is authenticated."""
        return self.user.is_authenticated
    
    @property
    def is_superuser(self) -> bool:
        """Check if the user is a superuser."""
        return getattr(self.user, "is_superuser", False)
    
    @property
    def membership(self) -> Optional["TenantMembership"]:
        """
        Get the user's membership in the current tenant.
        
        Returns:
            TenantMembership instance or None if not a member
        """
        if self._membership_cache is None:
            self._membership_cache = self._get_membership()
        return self._membership_cache
    
    def _get_membership(self) -> Optional["TenantMembership"]:
        """Fetch the membership from the database."""
        from tenant_authx.models import TenantMembership
        
        try:
            return TenantMembership.objects.select_related(
                "tenant"
            ).prefetch_related(
                "roles__permissions"
            ).get(
                user=self.user,
                tenant=self.tenant,
                is_active=True,
            )
        except TenantMembership.DoesNotExist:
            return None
    
    def is_member(self) -> bool:
        """
        Check if the user is a member of the current tenant.
        
        Returns:
            True if the user has an active membership in the tenant
        """
        if self._is_member_cache is None:
            self._is_member_cache = self.membership is not None
        return self._is_member_cache
    
    def has_perm(self, perm: str, obj=None) -> bool:
        """
        Check if the user has a permission within this tenant.
        
        Args:
            perm: Permission string in format 'app_label.codename'
            obj: Optional object for object-level permission checking
            
        Returns:
            True if the user has the permission, False otherwise
        """
        result = PermissionChecker.check_permission(
            user=self.user,
            tenant=self.tenant,
            permission_codename=perm,
            membership=self.membership,
        )
        
        # Log permission check
        audit_log(
            event="permission_check",
            user=self.user,
            tenant=self.tenant,
            permission=perm,
            success=result,
        )
        
        return result
    
    def has_perms(self, perm_list) -> bool:
        """
        Check if the user has all permissions in the list.
        
        Args:
            perm_list: Iterable of permission strings
            
        Returns:
            True if the user has all permissions, False otherwise
        """
        return all(self.has_perm(perm) for perm in perm_list)
    
    def get_all_permissions(self) -> Set[str]:
        """
        Get all permission codenames the user has in this tenant.
        
        Returns:
            Set of permission codename strings
        """
        if self._permission_cache is None:
            self._permission_cache = PermissionChecker.get_user_permissions(
                user=self.user,
                tenant=self.tenant,
                membership=self.membership,
            )
        return self._permission_cache
    
    def get_roles(self) -> list:
        """
        Get all roles assigned to the user in this tenant.
        
        Returns:
            List of Role instances
        """
        if not self.membership:
            return []
        return list(self.membership.roles.filter(is_active=True))
    
    def __str__(self) -> str:
        return f"{self.user} @ {self.tenant}"
    
    def __repr__(self) -> str:
        return f"<TenantUser: {self.user} @ {self.tenant.slug}>"


class PermissionChecker:
    """
    Core engine for evaluating tenant-scoped permissions.
    
    This class provides static methods for checking permissions
    and retrieving permission sets. It handles superuser bypass,
    membership verification, and role-based permission lookup.
    """
    
    @staticmethod
    def check_permission(
        user: "AbstractUser",
        tenant: "Tenant",
        permission_codename: str,
        membership: Optional["TenantMembership"] = None,
    ) -> bool:
        """
        Check if a user has a specific permission in a tenant.
        
        Algorithm:
        1. If user.is_superuser and SUPERUSER_BYPASS is True, return True
        2. Get active membership for user in tenant
        3. If no membership, return False
        4. Get all roles from membership
        5. Check if any role has permission with matching codename
        6. Return result
        
        Args:
            user: The user to check permissions for
            tenant: The tenant context
            permission_codename: The permission to check (e.g., 'app.view_model')
            membership: Optional pre-fetched membership (for optimization)
            
        Returns:
            True if the user has the permission, False otherwise
        """
        # Superuser bypass
        if (
            tenant_authx_settings.SUPERUSER_BYPASS
            and getattr(user, "is_superuser", False)
        ):
            return True
        
        # Validate tenant context
        try:
            validate_tenant_context(tenant)
        except Exception:
            return False
        
        # Get membership if not provided
        if membership is None:
            from tenant_authx.models import TenantMembership
            try:
                membership = TenantMembership.objects.get(
                    user=user,
                    tenant=tenant,
                    is_active=True,
                )
            except TenantMembership.DoesNotExist:
                return False
        
        # Check if any role has the permission
        return membership.has_permission(permission_codename)
    
    @staticmethod
    def get_user_permissions(
        user: "AbstractUser",
        tenant: "Tenant",
        membership: Optional["TenantMembership"] = None,
    ) -> Set[str]:
        """
        Get all permission codenames a user has in a tenant.
        
        Args:
            user: The user to get permissions for
            tenant: The tenant context
            membership: Optional pre-fetched membership (for optimization)
            
        Returns:
            Set of permission codename strings
        """
        # Superuser gets all permissions
        if (
            tenant_authx_settings.SUPERUSER_BYPASS
            and getattr(user, "is_superuser", False)
        ):
            from tenant_authx.models import Permission
            return set(
                Permission.objects.filter(
                    tenant=tenant
                ).values_list("codename", flat=True)
            )
        
        # Get membership if not provided
        if membership is None:
            from tenant_authx.models import TenantMembership
            try:
                membership = TenantMembership.objects.prefetch_related(
                    "roles__permissions"
                ).get(
                    user=user,
                    tenant=tenant,
                    is_active=True,
                )
            except TenantMembership.DoesNotExist:
                return set()
        
        return membership.get_permissions()
    
    @staticmethod
    def has_any_permission(
        user: "AbstractUser",
        tenant: "Tenant",
        permissions: list,
        membership: Optional["TenantMembership"] = None,
    ) -> bool:
        """
        Check if the user has ANY of the specified permissions.
        
        Args:
            user: The user to check
            tenant: The tenant context
            permissions: List of permission codenames
            membership: Optional pre-fetched membership
            
        Returns:
            True if user has at least one permission, False otherwise
        """
        for perm in permissions:
            if PermissionChecker.check_permission(
                user, tenant, perm, membership
            ):
                return True
        return False
    
    @staticmethod
    def has_all_permissions(
        user: "AbstractUser",
        tenant: "Tenant",
        permissions: list,
        membership: Optional["TenantMembership"] = None,
    ) -> bool:
        """
        Check if the user has ALL of the specified permissions.
        
        Args:
            user: The user to check
            tenant: The tenant context
            permissions: List of permission codenames
            membership: Optional pre-fetched membership
            
        Returns:
            True if user has all permissions, False otherwise
        """
        for perm in permissions:
            if not PermissionChecker.check_permission(
                user, tenant, perm, membership
            ):
                return False
        return True
