"""
Demo URL configuration.

Demonstrates tenant-aware URL patterns.
"""

from django.contrib import admin
from django.urls import path, include

from demo.core import views

urlpatterns = [
    # Admin (exempt from tenant resolution)
    path("admin/", admin.site.urls),
    
    # Public endpoints (no tenant required)
    path("", views.home, name="home"),
    path("accounts/login/", views.login_view, name="login"),
    path("accounts/logout/", views.logout_view, name="logout"),
    
    # Tenant-scoped endpoints
    path("t/<slug:tenant_slug>/", include([
        path("", views.tenant_dashboard, name="tenant_dashboard"),
        path("orders/", views.order_list, name="order_list"),
        path("orders/<uuid:order_id>/", views.order_detail, name="order_detail"),
        path("settings/", views.tenant_settings, name="tenant_settings"),
        
        # API endpoints
        path("api/", include("demo.core.api_urls")),
    ])),
]
