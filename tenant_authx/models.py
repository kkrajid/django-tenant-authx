"""
Core data models for django-tenant-authx.

Defines the Tenant, TenantMembership, Role, and Permission models
that form the foundation of tenant-aware authentication and authorization.
"""

import re
import uuid
from typing import Set

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


# Permission codename validation pattern
PERMISSION_CODENAME_REGEX = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")


class Tenant(models.Model):
    """
    Represents an isolated organizational unit within the SaaS application.
    
    Each tenant operates as an independent entity with its own users,
    roles, permissions, and data. Users can belong to multiple tenants
    with different roles in each.
    
    Attributes:
        id: UUID primary key (prevents enumeration attacks)
        name: Human-readable display name
        slug: URL-friendly unique identifier
        domain: Optional custom domain for the tenant
        is_active: Whether the tenant is currently active
        metadata: JSON field for custom tenant data
        created_at: Timestamp of creation
        updated_at: Timestamp of last update
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text=_("Unique identifier for the tenant")
    )
    
    name = models.CharField(
        max_length=255,
        help_text=_("Display name of the tenant")
    )
    
    slug = models.SlugField(
        max_length=100,
        unique=True,
        help_text=_("URL-friendly identifier (must be unique)")
    )
    
    domain = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        help_text=_("Custom domain for tenant (optional)")
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text=_("Whether the tenant is currently active")
    )
    
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Custom metadata for the tenant")
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_("When the tenant was created")
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text=_("When the tenant was last updated")
    )
    
    class Meta:
        db_table = "tenant_authx_tenant"
        ordering = ["name"]
        verbose_name = _("Tenant")
        verbose_name_plural = _("Tenants")
    
    def __str__(self) -> str:
        return self.name
    
    def clean(self):
        """Validate the tenant before saving."""
        super().clean()
        
        # Normalize slug to lowercase
        if self.slug:
            self.slug = self.slug.lower()
        
        # Normalize domain to lowercase if provided
        if self.domain:
            self.domain = self.domain.lower()
    
    def get_members(self, active_only: bool = True):
        """
        Get all users who are members of this tenant.
        
        Args:
            active_only: Only return users with active memberships
            
        Returns:
            QuerySet of User instances
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        memberships = self.memberships.all()
        if active_only:
            memberships = memberships.filter(is_active=True)
        
        user_ids = memberships.values_list("user_id", flat=True)
        return User.objects.filter(pk__in=user_ids)
    
    def get_membership(self, user):
        """
        Get the membership for a specific user.
        
        Args:
            user: The user to get membership for
            
        Returns:
            TenantMembership instance or None
        """
        try:
            return self.memberships.get(user=user)
        except TenantMembership.DoesNotExist:
            return None
    
    def add_member(self, user, roles=None, is_active: bool = True):
        """
        Add a user as a member of this tenant.
        
        Args:
            user: The user to add
            roles: Optional list of Role instances to assign
            is_active: Whether the membership should be active
            
        Returns:
            The created TenantMembership instance
            
        Raises:
            ValidationError: If user is already a member
        """
        membership, created = TenantMembership.objects.get_or_create(
            user=user,
            tenant=self,
            defaults={"is_active": is_active}
        )
        
        if not created:
            raise ValidationError(
                f"User {user} is already a member of tenant {self}"
            )
        
        if roles:
            membership.roles.set(roles)
        
        return membership


class TenantMembership(models.Model):
    """
    Links a User to a Tenant with associated roles.
    
    This is the through model that connects users to tenants,
    storing the relationship along with role assignments and
    membership status.
    
    Attributes:
        id: UUID primary key
        user: Foreign key to the user
        tenant: Foreign key to the tenant
        roles: Many-to-many relationship with Role
        is_active: Whether the membership is active
        joined_at: When the user joined the tenant
        updated_at: When the membership was last modified
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tenant_memberships",
        help_text=_("The user who is a member")
    )
    
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="memberships",
        help_text=_("The tenant the user belongs to")
    )
    
    roles = models.ManyToManyField(
        "Role",
        related_name="memberships",
        blank=True,
        help_text=_("Roles assigned to this user in this tenant")
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text=_("Whether the membership is currently active")
    )
    
    joined_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_("When the user joined the tenant")
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text=_("When the membership was last updated")
    )
    
    class Meta:
        db_table = "tenant_authx_membership"
        unique_together = [["user", "tenant"]]
        indexes = [
            models.Index(fields=["user", "tenant"]),
            models.Index(fields=["tenant", "is_active"]),
        ]
        verbose_name = _("Tenant Membership")
        verbose_name_plural = _("Tenant Memberships")
    
    def __str__(self) -> str:
        return f"{self.user} @ {self.tenant}"
    
    def get_permissions(self) -> Set[str]:
        """
        Get all permission codenames for this membership.
        
        Returns:
            Set of permission codenames
        """
        return set(
            self.roles.filter(
                is_active=True
            ).values_list(
                "permissions__codename", flat=True
            ).distinct()
        ) - {None}  # Remove None values from unassigned permissions
    
    def has_permission(self, permission_codename: str) -> bool:
        """
        Check if this membership has a specific permission.
        
        Args:
            permission_codename: The permission to check (e.g., 'app.view_model')
            
        Returns:
            True if the permission is granted, False otherwise
        """
        return self.roles.filter(
            is_active=True,
            permissions__codename=permission_codename
        ).exists()
    
    def add_role(self, role: "Role"):
        """
        Add a role to this membership.
        
        Args:
            role: The Role instance to add
            
        Raises:
            ValidationError: If role belongs to a different tenant
        """
        if role.tenant_id != self.tenant_id:
            raise ValidationError(
                f"Role '{role.name}' belongs to tenant '{role.tenant}', "
                f"not '{self.tenant}'"
            )
        self.roles.add(role)
    
    def remove_role(self, role: "Role"):
        """
        Remove a role from this membership.
        
        Args:
            role: The Role instance to remove
        """
        self.roles.remove(role)


class Role(models.Model):
    """
    A named collection of permissions within a tenant.
    
    Roles are scoped to a specific tenant, allowing each tenant
    to define their own role hierarchy and permission structure.
    
    Attributes:
        id: UUID primary key
        tenant: The tenant this role belongs to
        name: Human-readable role name
        description: Optional description of the role
        permissions: Many-to-many relationship with Permission
        is_active: Whether the role is active
        created_at: When the role was created
        updated_at: When the role was last modified
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="roles",
        help_text=_("The tenant this role belongs to")
    )
    
    name = models.CharField(
        max_length=100,
        help_text=_("Display name of the role")
    )
    
    description = models.TextField(
        blank=True,
        default="",
        help_text=_("Description of the role's purpose")
    )
    
    permissions = models.ManyToManyField(
        "Permission",
        related_name="roles",
        blank=True,
        help_text=_("Permissions granted by this role")
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text=_("Whether the role is currently active")
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_("When the role was created")
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text=_("When the role was last updated")
    )
    
    class Meta:
        db_table = "tenant_authx_role"
        unique_together = [["tenant", "name"]]
        indexes = [
            models.Index(fields=["tenant", "name"]),
        ]
        ordering = ["tenant", "name"]
        verbose_name = _("Role")
        verbose_name_plural = _("Roles")
    
    def __str__(self) -> str:
        return f"{self.name} ({self.tenant.slug})"
    
    def get_permissions(self) -> Set[str]:
        """
        Get all permission codenames for this role.
        
        Returns:
            Set of permission codenames
        """
        return set(
            self.permissions.values_list("codename", flat=True)
        )
    
    def add_permission(self, permission: "Permission"):
        """
        Add a permission to this role.
        
        Args:
            permission: The Permission instance to add
            
        Raises:
            ValidationError: If permission belongs to a different tenant
        """
        if permission.tenant_id != self.tenant_id:
            raise ValidationError(
                f"Permission '{permission.codename}' belongs to tenant "
                f"'{permission.tenant}', not '{self.tenant}'"
            )
        self.permissions.add(permission)


class Permission(models.Model):
    """
    A specific authorization grant within a tenant.
    
    Permissions use Django-style codenames in the format 'app_label.action_model'.
    They are scoped to a specific tenant for complete isolation.
    
    Attributes:
        id: UUID primary key
        tenant: The tenant this permission belongs to
        codename: Django-style permission code (e.g., 'orders.view_order')
        name: Human-readable permission name
        description: Optional description of what the permission grants
        created_at: When the permission was created
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="permissions",
        help_text=_("The tenant this permission belongs to")
    )
    
    codename = models.CharField(
        max_length=100,
        help_text=_("Permission code in format 'app_label.action_model'")
    )
    
    name = models.CharField(
        max_length=255,
        help_text=_("Human-readable name for the permission")
    )
    
    description = models.TextField(
        blank=True,
        default="",
        help_text=_("Description of what this permission grants")
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_("When the permission was created")
    )
    
    class Meta:
        db_table = "tenant_authx_permission"
        unique_together = [["tenant", "codename"]]
        indexes = [
            models.Index(fields=["tenant", "codename"]),
        ]
        ordering = ["tenant", "codename"]
        verbose_name = _("Permission")
        verbose_name_plural = _("Permissions")
    
    def __str__(self) -> str:
        return f"{self.codename} ({self.tenant.slug})"
    
    def clean(self):
        """Validate the permission before saving."""
        super().clean()
        
        # Validate codename format
        if self.codename and not PERMISSION_CODENAME_REGEX.match(self.codename):
            raise ValidationError({
                "codename": _(
                    "Permission codename must be in format 'app_label.action_model' "
                    "(lowercase, underscores allowed). "
                    f"Got: '{self.codename}'"
                )
            })
    
    def save(self, *args, **kwargs):
        """Save with validation."""
        self.full_clean()
        super().save(*args, **kwargs)
