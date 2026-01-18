"""
DRF permission classes for django-tenant-authx.

Provides permission classes for tenant-scoped authorization in REST APIs.
"""

from typing import List, Optional, TYPE_CHECKING

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from tenant_authx.permissions import TenantUser
from tenant_authx.utils import audit_log

if TYPE_CHECKING:
    from tenant_authx.models import Tenant


class IsTenantMember(BasePermission):
    """
    Permission class that requires the user to be a member of the current tenant.
    
    This is the most basic tenant permission - it only checks membership,
    not specific permissions.
    
    Usage:
        class MyViewSet(viewsets.ModelViewSet):
            permission_classes = [IsTenantMember]
    """
    
    message = "You must be a member of this tenant."
    
    def has_permission(self, request: Request, view: APIView) -> bool:
        """
        Check if user is a member of the current tenant.
        
        Args:
            request: The DRF request
            view: The view being accessed
            
        Returns:
            True if user is a tenant member
        """
        # Must be authenticated
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Must have tenant context
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return False
        
        # Superusers pass
        if getattr(request.user, "is_superuser", False):
            return True
        
        # Check membership via TenantUser
        tenant_user = getattr(request, "tenant_user", None)
        if tenant_user is None:
            tenant_user = TenantUser(user=request.user, tenant=tenant)
        
        is_member = tenant_user.is_member()
        
        if not is_member:
            audit_log(
                event="api_permission_denied",
                user=request.user,
                tenant=tenant,
                success=False,
                extra={"reason": "not_tenant_member", "view": view.__class__.__name__},
            )
        
        return is_member


class TenantPermission(BasePermission):
    """
    Base permission class for tenant-scoped permissions.
    
    Subclass this and set `required_permissions` to check specific permissions.
    
    Usage:
        class CanViewOrders(TenantPermission):
            required_permissions = ['orders.view_order']
        
        class MyViewSet(viewsets.ModelViewSet):
            permission_classes = [CanViewOrders]
    """
    
    # Override in subclasses
    required_permissions: List[str] = []
    
    # If True, require ALL permissions; if False, require ANY
    require_all: bool = True
    
    message = "You do not have permission to perform this action."
    
    def has_permission(self, request: Request, view: APIView) -> bool:
        """
        Check if user has required permissions in the current tenant.
        
        Args:
            request: The DRF request
            view: The view being accessed
            
        Returns:
            True if user has required permissions
        """
        # Must be authenticated
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Must have tenant context
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return False
        
        # Superusers pass
        if getattr(request.user, "is_superuser", False):
            return True
        
        # Get TenantUser
        tenant_user = getattr(request, "tenant_user", None)
        if tenant_user is None:
            tenant_user = TenantUser(user=request.user, tenant=tenant)
        
        # Check membership first
        if not tenant_user.is_member():
            return False
        
        # Get permissions to check (from class or view)
        perms = self.get_required_permissions(request, view)
        
        if not perms:
            # No permissions required, just membership
            return True
        
        # Check permissions
        if self.require_all:
            has_perms = tenant_user.has_perms(perms)
        else:
            has_perms = any(tenant_user.has_perm(p) for p in perms)
        
        if not has_perms:
            audit_log(
                event="api_permission_denied",
                user=request.user,
                tenant=tenant,
                permission=str(perms),
                success=False,
                extra={
                    "reason": "permission_denied",
                    "required": perms,
                    "view": view.__class__.__name__,
                },
            )
        
        return has_perms
    
    def get_required_permissions(
        self,
        request: Request,
        view: APIView
    ) -> List[str]:
        """
        Get the list of permissions to check.
        
        Override this method for dynamic permission checking.
        
        Args:
            request: The DRF request
            view: The view being accessed
            
        Returns:
            List of permission codenames
        """
        # First check view's permission attribute
        view_perms = getattr(view, "required_permissions", None)
        if view_perms:
            return view_perms
        
        # Fall back to class attribute
        return self.required_permissions
    
    def has_object_permission(
        self,
        request: Request,
        view: APIView,
        obj
    ) -> bool:
        """
        Check object-level permissions.
        
        By default, defers to has_permission. Override for object-specific checks.
        
        Args:
            request: The DRF request
            view: The view being accessed
            obj: The object being accessed
            
        Returns:
            True if user has permission on the object
        """
        return self.has_permission(request, view)


class HasTenantPermission(TenantPermission):
    """
    Configurable permission class that reads permissions from the view.
    
    Set `required_permissions` on your view to specify what's needed.
    
    Usage:
        class OrderViewSet(viewsets.ModelViewSet):
            permission_classes = [HasTenantPermission]
            required_permissions = ['orders.view_order']
        
        # Or with action-based permissions:
        class OrderViewSet(viewsets.ModelViewSet):
            permission_classes = [HasTenantPermission]
            
            def get_permissions(self):
                if self.action == 'create':
                    self.required_permissions = ['orders.add_order']
                elif self.action in ['update', 'partial_update']:
                    self.required_permissions = ['orders.change_order']
                elif self.action == 'destroy':
                    self.required_permissions = ['orders.delete_order']
                else:
                    self.required_permissions = ['orders.view_order']
                return super().get_permissions()
    """
    pass


class TenantObjectPermission(TenantPermission):
    """
    Permission class for object-level tenant permissions.
    
    Extends TenantPermission with object-level checks.
    Override `has_object_permission` for custom object-level logic.
    
    Usage:
        class IsObjectOwner(TenantObjectPermission):
            def has_object_permission(self, request, view, obj):
                # First check base permissions
                if not super().has_object_permission(request, view, obj):
                    return False
                # Then check ownership
                return obj.owner == request.user
    """
    
    def has_object_permission(
        self,
        request: Request,
        view: APIView,
        obj
    ) -> bool:
        """
        Check object-level permissions.
        
        Override this method for object-specific authorization logic.
        
        Args:
            request: The DRF request
            view: The view being accessed
            obj: The object being accessed
            
        Returns:
            True if user has permission on the object
        """
        # First verify view-level permission
        if not self.has_permission(request, view):
            return False
        
        # Check that object belongs to current tenant (if applicable)
        tenant = getattr(request, "tenant", None)
        obj_tenant = getattr(obj, "tenant", None)
        
        if tenant and obj_tenant:
            if obj_tenant.pk != tenant.pk:
                audit_log(
                    event="api_permission_denied",
                    user=request.user,
                    tenant=tenant,
                    success=False,
                    extra={
                        "reason": "cross_tenant_access",
                        "object_tenant": str(obj_tenant.pk),
                        "view": view.__class__.__name__,
                    },
                )
                return False
        
        return True


class TenantAdminPermission(TenantPermission):
    """
    Permission class requiring tenant admin role.
    
    Checks if the user has a role named 'Admin' (configurable)
    in the current tenant.
    
    Usage:
        class TenantSettingsView(APIView):
            permission_classes = [TenantAdminPermission]
    """
    
    admin_role_name = "Admin"
    message = "You must be a tenant administrator."
    
    def has_permission(self, request: Request, view: APIView) -> bool:
        """
        Check if user is a tenant admin.
        """
        # Must be authenticated
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Must have tenant context
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return False
        
        # Superusers pass
        if getattr(request.user, "is_superuser", False):
            return True
        
        # Get TenantUser
        tenant_user = getattr(request, "tenant_user", None)
        if tenant_user is None:
            tenant_user = TenantUser(user=request.user, tenant=tenant)
        
        # Check for admin role
        user_roles = {role.name for role in tenant_user.get_roles()}
        return self.admin_role_name in user_roles
