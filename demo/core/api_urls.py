"""Demo API URL configuration."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .api import OrderViewSet, TenantInfoViewSet

router = DefaultRouter()
router.register(r"orders", OrderViewSet, basename="order")
router.register(r"tenant", TenantInfoViewSet, basename="tenant")

urlpatterns = [
    path("", include(router.urls)),
]
