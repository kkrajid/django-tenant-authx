"""
Tests for tenant_authx permissions system.
"""

import pytest
from django.contrib.auth import get_user_model

from tenant_authx.models import (
    Tenant,
    TenantMembership,
    Role,
    Permission,
)
from tenant_authx.permissions import TenantUser, PermissionChecker


User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def superuser(db):
    """Create a test superuser."""
    return User.objects.create_superuser(
        username="superuser",
        email="super@example.com",
        password="superpass123",
    )


@pytest.fixture
def tenant(db):
    """Create a test tenant."""
    return Tenant.objects.create(
        name="Test Tenant",
        slug="test-tenant",
    )


@pytest.fixture
def other_tenant(db):
    """Create another tenant for isolation tests."""
    return Tenant.objects.create(
        name="Other Tenant",
        slug="other-tenant",
    )


@pytest.fixture
def permission(db, tenant):
    """Create a test permission."""
    return Permission.objects.create(
        tenant=tenant,
        codename="orders.view_order",
        name="Can view orders",
    )


@pytest.fixture
def other_permission(db, tenant):
    """Create another test permission."""
    return Permission.objects.create(
        tenant=tenant,
        codename="orders.edit_order",
        name="Can edit orders",
    )


@pytest.fixture
def role(db, tenant, permission):
    """Create a test role with permissions."""
    role = Role.objects.create(
        tenant=tenant,
        name="Manager",
    )
    role.permissions.add(permission)
    return role


@pytest.fixture
def membership(db, user, tenant, role):
    """Create a membership with roles."""
    membership = TenantMembership.objects.create(
        user=user,
        tenant=tenant,
    )
    membership.roles.add(role)
    return membership


class TestTenantUser:
    """Tests for TenantUser class."""
    
    def test_create_tenant_user(self, user, tenant):
        """Test creating a TenantUser."""
        tenant_user = TenantUser(user=user, tenant=tenant)
        assert tenant_user.user == user
        assert tenant_user.tenant == tenant
    
    def test_is_authenticated(self, user, tenant):
        """Test is_authenticated property."""
        tenant_user = TenantUser(user=user, tenant=tenant)
        assert tenant_user.is_authenticated is True
    
    def test_is_superuser(self, superuser, tenant):
        """Test is_superuser property."""
        tenant_user = TenantUser(user=superuser, tenant=tenant)
        assert tenant_user.is_superuser is True
    
    def test_is_member_true(self, user, tenant, membership):
        """Test is_member returns True for members."""
        tenant_user = TenantUser(user=user, tenant=tenant)
        assert tenant_user.is_member() is True
    
    def test_is_member_false(self, user, other_tenant):
        """Test is_member returns False for non-members."""
        tenant_user = TenantUser(user=user, tenant=other_tenant)
        assert tenant_user.is_member() is False
    
    def test_has_perm_granted(self, user, tenant, permission, membership):
        """Test has_perm returns True when permission is granted."""
        tenant_user = TenantUser(user=user, tenant=tenant)
        assert tenant_user.has_perm(permission.codename) is True
    
    def test_has_perm_denied(self, user, tenant, membership):
        """Test has_perm returns False for non-granted permission."""
        tenant_user = TenantUser(user=user, tenant=tenant)
        assert tenant_user.has_perm("nonexistent.permission") is False
    
    def test_has_perm_superuser_bypass(self, superuser, tenant, permission):
        """Test superusers bypass permission checks."""
        tenant_user = TenantUser(user=superuser, tenant=tenant)
        assert tenant_user.has_perm(permission.codename) is True
        assert tenant_user.has_perm("any.permission") is True
    
    def test_has_perms_all_granted(self, user, tenant, role, permission, other_permission, membership):
        """Test has_perms with multiple permissions."""
        role.permissions.add(other_permission)
        tenant_user = TenantUser(user=user, tenant=tenant)
        assert tenant_user.has_perms([permission.codename, other_permission.codename]) is True
    
    def test_has_perms_partial_denied(self, user, tenant, permission, membership):
        """Test has_perms returns False when not all permissions granted."""
        tenant_user = TenantUser(user=user, tenant=tenant)
        assert tenant_user.has_perms([permission.codename, "other.permission"]) is False
    
    def test_get_all_permissions(self, user, tenant, permission, membership):
        """Test getting all permissions."""
        tenant_user = TenantUser(user=user, tenant=tenant)
        perms = tenant_user.get_all_permissions()
        assert permission.codename in perms
    
    def test_get_roles(self, user, tenant, role, membership):
        """Test getting all roles."""
        tenant_user = TenantUser(user=user, tenant=tenant)
        roles = tenant_user.get_roles()
        assert role in roles
    
    def test_str(self, user, tenant):
        """Test string representation."""
        tenant_user = TenantUser(user=user, tenant=tenant)
        assert str(user) in str(tenant_user)
        assert str(tenant) in str(tenant_user)


class TestPermissionChecker:
    """Tests for PermissionChecker class."""
    
    def test_check_permission_granted(self, user, tenant, permission, membership):
        """Test permission check returns True when granted."""
        result = PermissionChecker.check_permission(
            user=user,
            tenant=tenant,
            permission_codename=permission.codename,
        )
        assert result is True
    
    def test_check_permission_denied(self, user, tenant, membership):
        """Test permission check returns False when not granted."""
        result = PermissionChecker.check_permission(
            user=user,
            tenant=tenant,
            permission_codename="nonexistent.permission",
        )
        assert result is False
    
    def test_check_permission_no_membership(self, user, other_tenant, permission):
        """Test permission check returns False without membership."""
        result = PermissionChecker.check_permission(
            user=user,
            tenant=other_tenant,
            permission_codename=permission.codename,
        )
        assert result is False
    
    def test_check_permission_superuser(self, superuser, tenant, permission):
        """Test superuser bypasses permission checks."""
        result = PermissionChecker.check_permission(
            user=superuser,
            tenant=tenant,
            permission_codename=permission.codename,
        )
        assert result is True
    
    def test_get_user_permissions(self, user, tenant, permission, membership):
        """Test getting all user permissions."""
        perms = PermissionChecker.get_user_permissions(
            user=user,
            tenant=tenant,
        )
        assert permission.codename in perms
    
    def test_has_any_permission(self, user, tenant, permission, membership):
        """Test has_any_permission returns True when any matches."""
        result = PermissionChecker.has_any_permission(
            user=user,
            tenant=tenant,
            permissions=[permission.codename, "other.permission"],
        )
        assert result is True
    
    def test_has_any_permission_none_match(self, user, tenant, membership):
        """Test has_any_permission returns False when none match."""
        result = PermissionChecker.has_any_permission(
            user=user,
            tenant=tenant,
            permissions=["perm1", "perm2"],
        )
        assert result is False
    
    def test_has_all_permissions(self, user, tenant, role, permission, other_permission, membership):
        """Test has_all_permissions returns True when all match."""
        role.permissions.add(other_permission)
        result = PermissionChecker.has_all_permissions(
            user=user,
            tenant=tenant,
            permissions=[permission.codename, other_permission.codename],
        )
        assert result is True
    
    def test_has_all_permissions_partial(self, user, tenant, permission, membership):
        """Test has_all_permissions returns False when partial match."""
        result = PermissionChecker.has_all_permissions(
            user=user,
            tenant=tenant,
            permissions=[permission.codename, "other.permission"],
        )
        assert result is False


class TestTenantIsolation:
    """Tests for tenant permission isolation."""
    
    def test_permission_isolated_to_tenant(self, user, tenant, other_tenant, permission, membership):
        """Test permissions in one tenant don't apply to another."""
        # User has permission in tenant
        assert PermissionChecker.check_permission(
            user=user,
            tenant=tenant,
            permission_codename=permission.codename,
        ) is True
        
        # User doesn't have permission in other_tenant (no membership)
        assert PermissionChecker.check_permission(
            user=user,
            tenant=other_tenant,
            permission_codename=permission.codename,
        ) is False
    
    def test_different_roles_per_tenant(self, db, user, tenant, other_tenant):
        """Test user can have different roles in different tenants."""
        # Set up admin role in tenant
        admin_perm = Permission.objects.create(
            tenant=tenant,
            codename="admin.all",
            name="Admin access",
        )
        admin_role = Role.objects.create(tenant=tenant, name="Admin")
        admin_role.permissions.add(admin_perm)
        
        # Set up viewer role in other_tenant
        view_perm = Permission.objects.create(
            tenant=other_tenant,
            codename="viewer.view",
            name="View only",
        )
        viewer_role = Role.objects.create(tenant=other_tenant, name="Viewer")
        viewer_role.permissions.add(view_perm)
        
        # Add user to both tenants with different roles
        m1 = TenantMembership.objects.create(user=user, tenant=tenant)
        m1.roles.add(admin_role)
        
        m2 = TenantMembership.objects.create(user=user, tenant=other_tenant)
        m2.roles.add(viewer_role)
        
        # Check permissions are isolated
        assert PermissionChecker.check_permission(
            user=user,
            tenant=tenant,
            permission_codename="admin.all",
        ) is True
        
        assert PermissionChecker.check_permission(
            user=user,
            tenant=other_tenant,
            permission_codename="admin.all",
        ) is False
        
        assert PermissionChecker.check_permission(
            user=user,
            tenant=other_tenant,
            permission_codename="viewer.view",
        ) is True
