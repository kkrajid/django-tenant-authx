"""
View decorators for django-tenant-authx.

Provides decorators for protecting views with tenant-aware
authentication and permission checks.
"""

from functools import wraps
from typing import Callable, Union, List

from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse

from tenant_authx.permissions import TenantUser
from tenant_authx.utils import audit_log, normalize_permission_list


def tenant_login_required(
    view_func: Callable = None,
    redirect_field_name: str = REDIRECT_FIELD_NAME,
    login_url: str = None,
):
    """
    Decorator that requires the user to be authenticated and a member
    of the current tenant.
    
    Checks:
    1. User is authenticated
    2. request.tenant exists
    3. User has active membership in request.tenant
    
    If any check fails:
    - For unauthenticated users: Redirect to login page
    - For authenticated non-members: Return 403 Forbidden
    
    Usage:
        @tenant_login_required
        def my_view(request):
            ...
        
        @tenant_login_required(login_url='/custom-login/')
        def my_view(request):
            ...
    
    For class-based views, use as method_decorator:
        @method_decorator(tenant_login_required, name='dispatch')
        class MyView(View):
            ...
    
    Args:
        view_func: The view function to wrap
        redirect_field_name: URL query parameter for redirect destination
        login_url: Custom login URL (defaults to settings.LOGIN_URL)
        
    Returns:
        Decorated view function
    """
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def _wrapped_view(
            request: HttpRequest,
            *args,
            **kwargs
        ) -> HttpResponse:
            # Check authentication
            if not request.user.is_authenticated:
                path = request.build_absolute_uri()
                resolved_login_url = login_url or settings.LOGIN_URL
                return redirect_to_login(
                    path,
                    resolved_login_url,
                    redirect_field_name,
                )
            
            # Check tenant exists
            tenant = getattr(request, "tenant", None)
            if tenant is None:
                audit_log(
                    event="access_denied",
                    user=request.user,
                    request=request,
                    success=False,
                    extra={"reason": "no_tenant_context"},
                )
                raise PermissionDenied("No tenant context available")
            
            # Check tenant membership (superusers can bypass if configured)
            tenant_user = getattr(request, "tenant_user", None)
            if tenant_user is None:
                tenant_user = TenantUser(user=request.user, tenant=tenant)
            
            # Allow superusers to bypass membership check
            from tenant_authx.conf import tenant_authx_settings
            if tenant_authx_settings.SUPERUSER_BYPASS and request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            if not tenant_user.is_member():
                audit_log(
                    event="access_denied",
                    user=request.user,
                    tenant=tenant,
                    request=request,
                    success=False,
                    extra={"reason": "not_tenant_member"},
                )
                raise PermissionDenied(
                    f"You are not a member of {tenant.name}"
                )
            
            # All checks passed
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    
    if view_func:
        return decorator(view_func)
    return decorator


def tenant_permission_required(
    perm: Union[str, List[str]],
    redirect_field_name: str = REDIRECT_FIELD_NAME,
    login_url: str = None,
    raise_exception: bool = True,
    require_all: bool = True,
):
    """
    Decorator that requires the user to have specific permission(s)
    in the current tenant.
    
    Checks:
    1. User is authenticated
    2. request.tenant exists
    3. User has active membership in request.tenant
    4. User has required permission(s) in request.tenant
    
    Usage:
        @tenant_permission_required('orders.view_order')
        def order_detail(request, order_id):
            ...
        
        @tenant_permission_required(['orders.view_order', 'orders.edit_order'])
        def order_edit(request, order_id):
            ...
        
        @tenant_permission_required(
            'admin.manage_users',
            raise_exception=False,  # Redirect instead of 403
            login_url='/no-permission/'
        )
        def admin_view(request):
            ...
    
    Args:
        perm: Permission string or list of permission strings
        redirect_field_name: URL query parameter for redirect destination
        login_url: Custom redirect URL for permission failures
        raise_exception: If True, raise PermissionDenied; else redirect
        require_all: If True, require ALL permissions; else require ANY
        
    Returns:
        Decorated view function
    """
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def _wrapped_view(
            request: HttpRequest,
            *args,
            **kwargs
        ) -> HttpResponse:
            # First, apply tenant_login_required checks
            if not request.user.is_authenticated:
                path = request.build_absolute_uri()
                resolved_login_url = login_url or settings.LOGIN_URL
                return redirect_to_login(
                    path,
                    resolved_login_url,
                    redirect_field_name,
                )
            
            tenant = getattr(request, "tenant", None)
            if tenant is None:
                if raise_exception:
                    raise PermissionDenied("No tenant context available")
                return redirect_to_login(
                    request.build_absolute_uri(),
                    login_url or settings.LOGIN_URL,
                    redirect_field_name,
                )
            
            # Get or create TenantUser
            tenant_user = getattr(request, "tenant_user", None)
            if tenant_user is None:
                tenant_user = TenantUser(user=request.user, tenant=tenant)
            
            # Allow superusers to bypass all checks
            from tenant_authx.conf import tenant_authx_settings
            if tenant_authx_settings.SUPERUSER_BYPASS and request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # Check membership
            if not tenant_user.is_member():
                audit_log(
                    event="access_denied",
                    user=request.user,
                    tenant=tenant,
                    request=request,
                    success=False,
                    extra={"reason": "not_tenant_member"},
                )
                if raise_exception:
                    raise PermissionDenied(
                        f"You are not a member of {tenant.name}"
                    )
                return redirect_to_login(
                    request.build_absolute_uri(),
                    login_url or settings.LOGIN_URL,
                    redirect_field_name,
                )
            
            # Check permissions
            perm_list = normalize_permission_list(perm)
            
            if require_all:
                has_perms = tenant_user.has_perms(perm_list)
            else:
                has_perms = any(
                    tenant_user.has_perm(p) for p in perm_list
                )
            
            if not has_perms:
                audit_log(
                    event="access_denied",
                    user=request.user,
                    tenant=tenant,
                    permission=str(perm),
                    request=request,
                    success=False,
                    extra={"reason": "permission_denied", "required": perm_list},
                )
                if raise_exception:
                    raise PermissionDenied(
                        f"Permission denied: {perm}"
                    )
                return redirect_to_login(
                    request.build_absolute_uri(),
                    login_url or "/permission-denied/",
                    redirect_field_name,
                )
            
            # All checks passed
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    
    return decorator


def tenant_role_required(
    role_name: Union[str, List[str]],
    redirect_field_name: str = REDIRECT_FIELD_NAME,
    login_url: str = None,
    raise_exception: bool = True,
    require_all: bool = False,
):
    """
    Decorator that requires the user to have specific role(s)
    in the current tenant.
    
    Usage:
        @tenant_role_required('Admin')
        def admin_view(request):
            ...
        
        @tenant_role_required(['Admin', 'Manager'], require_all=False)
        def management_view(request):
            ...
    
    Args:
        role_name: Role name or list of role names
        redirect_field_name: URL query parameter for redirect destination
        login_url: Custom redirect URL for role check failures
        raise_exception: If True, raise PermissionDenied; else redirect
        require_all: If True, require ALL roles; else require ANY
        
    Returns:
        Decorated view function
    """
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def _wrapped_view(
            request: HttpRequest,
            *args,
            **kwargs
        ) -> HttpResponse:
            # Authentication check
            if not request.user.is_authenticated:
                path = request.build_absolute_uri()
                resolved_login_url = login_url or settings.LOGIN_URL
                return redirect_to_login(
                    path,
                    resolved_login_url,
                    redirect_field_name,
                )
            
            tenant = getattr(request, "tenant", None)
            if tenant is None:
                if raise_exception:
                    raise PermissionDenied("No tenant context available")
                return redirect_to_login(
                    request.build_absolute_uri(),
                    login_url or settings.LOGIN_URL,
                    redirect_field_name,
                )
            
            # Get or create TenantUser
            tenant_user = getattr(request, "tenant_user", None)
            if tenant_user is None:
                tenant_user = TenantUser(user=request.user, tenant=tenant)
            
            # Allow superusers to bypass all checks
            from tenant_authx.conf import tenant_authx_settings
            if tenant_authx_settings.SUPERUSER_BYPASS and request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # Check membership
            if not tenant_user.is_member():
                if raise_exception:
                    raise PermissionDenied(
                        f"You are not a member of {tenant.name}"
                    )
                return redirect_to_login(
                    request.build_absolute_uri(),
                    login_url or settings.LOGIN_URL,
                    redirect_field_name,
                )
            
            # Check roles
            role_names = normalize_permission_list(role_name)
            user_roles = {role.name for role in tenant_user.get_roles()}
            
            if require_all:
                has_roles = all(r in user_roles for r in role_names)
            else:
                has_roles = any(r in user_roles for r in role_names)
            
            if not has_roles:
                audit_log(
                    event="access_denied",
                    user=request.user,
                    tenant=tenant,
                    request=request,
                    success=False,
                    extra={
                        "reason": "role_required",
                        "required": role_names,
                        "user_roles": list(user_roles),
                    },
                )
                if raise_exception:
                    raise PermissionDenied(
                        f"Role required: {role_name}"
                    )
                return redirect_to_login(
                    request.build_absolute_uri(),
                    login_url or "/permission-denied/",
                    redirect_field_name,
                )
            
            # All checks passed
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    
    return decorator
