"""
Django admin integration for django-tenant-authx.

Provides admin classes for managing Tenants, TenantMemberships,
Roles, and Permissions.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from tenant_authx.models import (
    Tenant,
    TenantMembership,
    Role,
    Permission,
)


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    """
    Admin interface for Tenant model.
    
    Provides management of tenants with filtering, search,
    and automatic slug population.
    """
    
    list_display = [
        "name",
        "slug",
        "domain",
        "is_active",
        "member_count",
        "created_at",
    ]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "slug", "domain"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]
    
    fieldsets = (
        (None, {
            "fields": ("name", "slug", "is_active")
        }),
        (_("Domain Configuration"), {
            "fields": ("domain",),
            "classes": ("collapse",),
        }),
        (_("Metadata"), {
            "fields": ("metadata",),
            "classes": ("collapse",),
        }),
        (_("System Information"), {
            "fields": ("id", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )
    
    def member_count(self, obj):
        """Display the number of members in this tenant."""
        count = obj.memberships.filter(is_active=True).count()
        return count
    member_count.short_description = _("Members")
    member_count.admin_order_field = "memberships"


@admin.register(TenantMembership)
class TenantMembershipAdmin(admin.ModelAdmin):
    """
    Admin interface for TenantMembership model.
    
    Provides management of user-tenant relationships with role assignment.
    """
    
    list_display = [
        "user",
        "tenant",
        "is_active",
        "role_list",
        "joined_at",
    ]
    list_filter = ["is_active", "tenant", "joined_at", "roles"]
    search_fields = [
        "user__username",
        "user__email",
        "tenant__name",
        "tenant__slug",
    ]
    raw_id_fields = ["user"]
    filter_horizontal = ["roles"]
    readonly_fields = ["id", "joined_at", "updated_at"]
    ordering = ["-joined_at"]
    
    fieldsets = (
        (None, {
            "fields": ("user", "tenant", "is_active")
        }),
        (_("Roles"), {
            "fields": ("roles",),
        }),
        (_("System Information"), {
            "fields": ("id", "joined_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )
    
    def role_list(self, obj):
        """Display the roles assigned to this membership."""
        roles = obj.roles.filter(is_active=True).values_list("name", flat=True)
        return ", ".join(roles) if roles else "-"
    role_list.short_description = _("Roles")
    
    def formfield_for_manytomany(self, db_field, request, **kwargs):
        """Filter roles to only show roles from the selected tenant."""
        if db_field.name == "roles":
            # Get the object being edited
            obj_id = request.resolver_match.kwargs.get("object_id")
            if obj_id:
                try:
                    membership = TenantMembership.objects.get(pk=obj_id)
                    kwargs["queryset"] = Role.objects.filter(
                        tenant=membership.tenant,
                        is_active=True,
                    )
                except TenantMembership.DoesNotExist:
                    pass
        return super().formfield_for_manytomany(db_field, request, **kwargs)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """
    Admin interface for Role model.
    
    Provides management of tenant-scoped roles with permission assignment.
    """
    
    list_display = [
        "name",
        "tenant",
        "is_active",
        "permission_count",
        "membership_count",
        "created_at",
    ]
    list_filter = ["is_active", "tenant", "created_at"]
    search_fields = ["name", "description", "tenant__name", "tenant__slug"]
    filter_horizontal = ["permissions"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["tenant", "name"]
    
    fieldsets = (
        (None, {
            "fields": ("tenant", "name", "description", "is_active")
        }),
        (_("Permissions"), {
            "fields": ("permissions",),
        }),
        (_("System Information"), {
            "fields": ("id", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )
    
    def permission_count(self, obj):
        """Display the number of permissions in this role."""
        return obj.permissions.count()
    permission_count.short_description = _("Permissions")
    
    def membership_count(self, obj):
        """Display the number of memberships with this role."""
        return obj.memberships.filter(is_active=True).count()
    membership_count.short_description = _("Assignments")
    
    def formfield_for_manytomany(self, db_field, request, **kwargs):
        """Filter permissions to only show permissions from the same tenant."""
        if db_field.name == "permissions":
            obj_id = request.resolver_match.kwargs.get("object_id")
            if obj_id:
                try:
                    role = Role.objects.get(pk=obj_id)
                    kwargs["queryset"] = Permission.objects.filter(
                        tenant=role.tenant
                    )
                except Role.DoesNotExist:
                    pass
        return super().formfield_for_manytomany(db_field, request, **kwargs)


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    """
    Admin interface for Permission model.
    
    Provides management of tenant-scoped permissions.
    """
    
    list_display = [
        "name",
        "codename",
        "tenant",
        "role_count",
        "created_at",
    ]
    list_filter = ["tenant", "created_at"]
    search_fields = ["name", "codename", "description", "tenant__name"]
    readonly_fields = ["id", "created_at"]
    ordering = ["tenant", "codename"]
    
    fieldsets = (
        (None, {
            "fields": ("tenant", "codename", "name")
        }),
        (_("Details"), {
            "fields": ("description",),
        }),
        (_("System Information"), {
            "fields": ("id", "created_at"),
            "classes": ("collapse",),
        }),
    )
    
    def role_count(self, obj):
        """Display the number of roles that have this permission."""
        return obj.roles.filter(is_active=True).count()
    role_count.short_description = _("Roles")


# Optional: Inline admin for adding roles from membership edit page
class RoleInline(admin.TabularInline):
    """Inline for viewing/adding roles to a membership."""
    model = TenantMembership.roles.through
    extra = 1
    verbose_name = _("Role")
    verbose_name_plural = _("Roles")


# Optional: Inline admin for adding permissions from role edit page
class PermissionInline(admin.TabularInline):
    """Inline for viewing/adding permissions to a role."""
    model = Role.permissions.through
    extra = 1
    verbose_name = _("Permission")
    verbose_name_plural = _("Permissions")
