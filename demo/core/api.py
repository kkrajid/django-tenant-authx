"""
Demo API views showing DRF integration with tenant_authx.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import serializers

from tenant_authx.drf.authentication import TenantSessionAuthentication, TenantTokenAuthentication
from tenant_authx.drf.permissions import IsTenantMember, HasTenantPermission

from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer for OrderItem."""
    
    line_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = OrderItem
        fields = ["id", "product_name", "quantity", "unit_price", "line_total"]


class OrderSerializer(serializers.ModelSerializer):
    """Serializer for Order."""
    
    items = OrderItemSerializer(many=True, read_only=True)
    
    class Meta:
        model = Order
        fields = [
            "id", "order_number", "customer_name", "customer_email",
            "total_amount", "status", "items", "created_at", "updated_at"
        ]
        read_only_fields = ["id", "order_number", "created_at", "updated_at"]


class OrderViewSet(viewsets.ModelViewSet):
    """
    API ViewSet for Orders with tenant-aware permissions.
    
    This demonstrates:
    1. Using TenantSessionAuthentication for API auth
    2. Using IsTenantMember to require tenant membership
    3. Using HasTenantPermission for granular permissions
    4. Always filtering queryset by tenant
    """
    
    serializer_class = OrderSerializer
    
    # Tenant-aware authentication
    authentication_classes = [TenantSessionAuthentication, TenantTokenAuthentication]
    
    # Permission classes - require tenant membership
    permission_classes = [IsTenantMember]
    
    def get_queryset(self):
        """
        CRITICAL: Always filter by tenant!
        
        This ensures users can only see orders from their current tenant.
        """
        if not hasattr(self.request, "tenant") or self.request.tenant is None:
            return Order.objects.none()
        return Order.objects.filter(tenant=self.request.tenant)
    
    def perform_create(self, serializer):
        """Set tenant and created_by on new orders."""
        serializer.save(
            tenant=self.request.tenant,
            created_by=self.request.user,
        )
    
    @action(detail=True, methods=["post"])
    def ship(self, request, pk=None):
        """
        Ship an order - requires 'orders.change_order' permission.
        """
        # Check permission manually for this action
        if not request.tenant_user.has_perm("orders.change_order"):
            return Response(
                {"detail": "Permission denied"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        order = self.get_object()
        order.status = "shipped"
        order.save()
        return Response({"status": "shipped"})
    
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Cancel an order."""
        if not request.tenant_user.has_perm("orders.delete_order"):
            return Response(
                {"detail": "Permission denied"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        order = self.get_object()
        order.status = "cancelled"
        order.save()
        return Response({"status": "cancelled"})


class TenantInfoViewSet(viewsets.ViewSet):
    """
    API ViewSet for tenant information.
    
    Shows how to access tenant context in DRF views.
    """
    
    authentication_classes = [TenantSessionAuthentication]
    permission_classes = [IsTenantMember]
    
    def list(self, request):
        """Get current tenant info."""
        tenant = request.tenant
        tenant_user = request.tenant_user
        
        return Response({
            "tenant": {
                "id": str(tenant.pk),
                "name": tenant.name,
                "slug": tenant.slug,
            },
            "user": {
                "username": request.user.username,
                "is_member": tenant_user.is_member(),
                "roles": [role.name for role in tenant_user.get_roles()],
                "permissions": list(tenant_user.get_all_permissions()),
            }
        })
