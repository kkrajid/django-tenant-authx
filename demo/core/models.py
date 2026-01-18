"""
Demo models showing tenant-aware data models.
"""

import uuid
from django.db import models
from django.conf import settings

from tenant_authx.models import Tenant


class Order(models.Model):
    """
    Example tenant-scoped model.
    
    Every Order belongs to exactly one Tenant.
    Always filter by tenant in your queries!
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="orders",
        help_text="The tenant this order belongs to",
    )
    
    # Order data
    order_number = models.CharField(max_length=50)
    customer_name = models.CharField(max_length=255)
    customer_email = models.EmailField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    
    # Audit fields
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_orders",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "demo_order"
        ordering = ["-created_at"]
        # Important: Always include tenant in queries!
        indexes = [
            models.Index(fields=["tenant", "order_number"]),
            models.Index(fields=["tenant", "status"]),
        ]
    
    def __str__(self):
        return f"Order {self.order_number}"
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            # Generate order number
            count = Order.objects.filter(tenant=self.tenant).count() + 1
            self.order_number = f"ORD-{self.tenant.slug.upper()[:5]}-{count:05d}"
        super().save(*args, **kwargs)


class OrderItem(models.Model):
    """Order line item."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    
    product_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        db_table = "demo_order_item"
    
    def __str__(self):
        return f"{self.quantity}x {self.product_name}"
    
    @property
    def line_total(self):
        return self.quantity * self.unit_price
