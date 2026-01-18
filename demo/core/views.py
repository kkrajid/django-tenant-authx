"""
Demo views showing tenant-aware authentication and authorization.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.http import HttpResponse

from tenant_authx.decorators import tenant_login_required, tenant_permission_required
from tenant_authx.models import Tenant

from .models import Order


def home(request):
    """Public home page - no tenant required."""
    tenants = Tenant.objects.filter(is_active=True)
    return render(request, "home.html", {"tenants": tenants})


def login_view(request):
    """Login view."""
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            next_url = request.GET.get("next", "/")
            return redirect(next_url)
    else:
        form = AuthenticationForm()
    return render(request, "login.html", {"form": form})


def logout_view(request):
    """Logout view."""
    logout(request)
    return redirect("home")


@tenant_login_required
def tenant_dashboard(request, tenant_slug):
    """
    Tenant dashboard - requires authentication and membership.
    
    The @tenant_login_required decorator ensures:
    1. User is authenticated
    2. User is a member of request.tenant
    """
    tenant = request.tenant
    tenant_user = request.tenant_user
    
    # Get user's roles in this tenant
    roles = tenant_user.get_roles()
    
    # Get recent orders (always filter by tenant!)
    recent_orders = Order.objects.filter(tenant=tenant)[:5]
    
    context = {
        "tenant": tenant,
        "tenant_user": tenant_user,
        "roles": roles,
        "recent_orders": recent_orders,
        "permissions": tenant_user.get_all_permissions(),
    }
    return render(request, "dashboard.html", context)


@tenant_permission_required("orders.view_order")
def order_list(request, tenant_slug):
    """
    Order list - requires 'orders.view_order' permission.
    
    The @tenant_permission_required decorator ensures:
    1. User is authenticated
    2. User is a member of request.tenant
    3. User has 'orders.view_order' permission in this tenant
    """
    orders = Order.objects.filter(tenant=request.tenant)
    
    # Filter by status if provided
    status = request.GET.get("status")
    if status:
        orders = orders.filter(status=status)
    
    return render(request, "orders/list.html", {
        "orders": orders,
        "tenant": request.tenant,
    })


@tenant_permission_required("orders.view_order")
def order_detail(request, tenant_slug, order_id):
    """Order detail view."""
    order = get_object_or_404(
        Order,
        pk=order_id,
        tenant=request.tenant,  # Always include tenant filter!
    )
    return render(request, "orders/detail.html", {
        "order": order,
        "tenant": request.tenant,
    })


@tenant_permission_required("settings.manage_tenant")
def tenant_settings(request, tenant_slug):
    """
    Tenant settings - requires admin permission.
    
    Only users with 'settings.manage_tenant' can access this.
    """
    tenant = request.tenant
    
    if request.method == "POST":
        # Handle settings update
        tenant.name = request.POST.get("name", tenant.name)
        tenant.save()
        messages.success(request, "Settings updated successfully!")
        return redirect("tenant_settings", tenant_slug=tenant.slug)
    
    return render(request, "settings.html", {"tenant": tenant})
