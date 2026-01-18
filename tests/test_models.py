"""
Tests for tenant_authx models.
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from tenant_authx.models import (
    Tenant,
    TenantMembership,
    Role,
    Permission,
)


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
def tenant(db):
    """Create a test tenant."""
    return Tenant.objects.create(
        name="Test Tenant",
        slug="test-tenant",
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
def role(db, tenant, permission):
    """Create a test role with permissions."""
    role = Role.objects.create(
        tenant=tenant,
        name="Manager",
        description="Manager role",
    )
    role.permissions.add(permission)
    return role


@pytest.fixture
def membership(db, user, tenant, role):
    """Create a test membership with roles."""
    membership = TenantMembership.objects.create(
        user=user,
        tenant=tenant,
    )
    membership.roles.add(role)
    return membership


class TestTenantModel:
    """Tests for the Tenant model."""
    
    def test_create_tenant(self, db):
        """Test creating a tenant."""
        tenant = Tenant.objects.create(
            name="Acme Corp",
            slug="acme-corp",
        )
        assert tenant.pk is not None
        assert tenant.name == "Acme Corp"
        assert tenant.slug == "acme-corp"
        assert tenant.is_active is True
    
    def test_tenant_slug_unique(self, db, tenant):
        """Test that tenant slugs must be unique."""
        with pytest.raises(IntegrityError):
            Tenant.objects.create(
                name="Another Tenant",
                slug=tenant.slug,  # Duplicate slug
            )
    
    def test_tenant_domain_unique(self, db):
        """Test that tenant domains must be unique."""
        Tenant.objects.create(
            name="Tenant 1",
            slug="tenant-1",
            domain="tenant1.example.com",
        )
        with pytest.raises(IntegrityError):
            Tenant.objects.create(
                name="Tenant 2",
                slug="tenant-2",
                domain="tenant1.example.com",  # Duplicate domain
            )
    
    def test_tenant_str(self, tenant):
        """Test tenant string representation."""
        assert str(tenant) == "Test Tenant"
    
    def test_get_members(self, user, tenant, membership):
        """Test getting tenant members."""
        members = tenant.get_members()
        assert user in members
    
    def test_add_member(self, db, user, tenant):
        """Test adding a member to tenant."""
        membership = tenant.add_member(user)
        assert membership.user == user
        assert membership.tenant == tenant
        assert membership.is_active is True


class TestTenantMembershipModel:
    """Tests for the TenantMembership model."""
    
    def test_create_membership(self, db, user, tenant):
        """Test creating a membership."""
        membership = TenantMembership.objects.create(
            user=user,
            tenant=tenant,
        )
        assert membership.pk is not None
        assert membership.user == user
        assert membership.tenant == tenant
        assert membership.is_active is True
    
    def test_membership_unique_per_user_tenant(self, db, user, tenant):
        """Test that each user-tenant pair can have only one membership."""
        TenantMembership.objects.create(user=user, tenant=tenant)
        with pytest.raises(IntegrityError):
            TenantMembership.objects.create(user=user, tenant=tenant)
    
    def test_membership_str(self, membership):
        """Test membership string representation."""
        assert "@" in str(membership)
    
    def test_get_permissions(self, membership, permission):
        """Test getting permissions from membership."""
        perms = membership.get_permissions()
        assert permission.codename in perms
    
    def test_has_permission(self, membership, permission):
        """Test checking specific permission."""
        assert membership.has_permission(permission.codename) is True
        assert membership.has_permission("nonexistent.perm") is False


class TestRoleModel:
    """Tests for the Role model."""
    
    def test_create_role(self, db, tenant):
        """Test creating a role."""
        role = Role.objects.create(
            tenant=tenant,
            name="Admin",
            description="Admin role",
        )
        assert role.pk is not None
        assert role.name == "Admin"
        assert role.tenant == tenant
    
    def test_role_name_unique_per_tenant(self, db, tenant):
        """Test that role names are unique within a tenant."""
        Role.objects.create(tenant=tenant, name="Admin")
        with pytest.raises(IntegrityError):
            Role.objects.create(tenant=tenant, name="Admin")
    
    def test_role_same_name_different_tenants(self, db, tenant):
        """Test that same role name can exist in different tenants."""
        Role.objects.create(tenant=tenant, name="Admin")
        
        other_tenant = Tenant.objects.create(name="Other", slug="other")
        role2 = Role.objects.create(tenant=other_tenant, name="Admin")
        assert role2.pk is not None
    
    def test_role_str(self, role):
        """Test role string representation."""
        assert "Manager" in str(role)


class TestPermissionModel:
    """Tests for the Permission model."""
    
    def test_create_permission(self, db, tenant):
        """Test creating a permission."""
        perm = Permission.objects.create(
            tenant=tenant,
            codename="billing.view_invoice",
            name="Can view invoices",
        )
        assert perm.pk is not None
        assert perm.codename == "billing.view_invoice"
    
    def test_permission_codename_validation(self, db, tenant):
        """Test permission codename format validation."""
        # Invalid format should raise error
        perm = Permission(
            tenant=tenant,
            codename="InvalidFormat",  # Wrong format
            name="Invalid",
        )
        with pytest.raises(ValidationError):
            perm.full_clean()
    
    def test_permission_codename_unique_per_tenant(self, db, tenant):
        """Test permission codenames are unique within a tenant."""
        Permission.objects.create(
            tenant=tenant,
            codename="app.action_model",
            name="Test permission",
        )
        # Permission.save() calls full_clean() which raises ValidationError
        # before the database IntegrityError is reached
        with pytest.raises((ValidationError, IntegrityError)):
            Permission.objects.create(
                tenant=tenant,
                codename="app.action_model",  # Duplicate
                name="Another permission",
            )
    
    def test_permission_str(self, permission):
        """Test permission string representation."""
        assert permission.codename in str(permission)
