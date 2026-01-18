"""
Property-based tests for tenant_authx models using Hypothesis.

These tests validate universal correctness properties that should hold
for all valid inputs, not just specific examples.
"""

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError

from tenant_authx.models import Tenant, TenantMembership, Role, Permission
from tests.strategies import (
    slug_strategy,
    domain_strategy,
    tenant_name_strategy,
    role_name_strategy,
    permission_codename_strategy,
    username_strategy,
)


User = get_user_model()


# Suppress database health check since we're using Django's test DB
hypothesis_settings = settings(
    max_examples=25,
    deadline=None,
)


@pytest.mark.django_db(transaction=True)
class TestTenantProperties:
    """Property-based tests for Tenant model."""
    
    @hypothesis_settings
    @given(name=tenant_name_strategy, slug=slug_strategy)
    def test_tenant_creation_with_valid_data(self, name, slug):
        """Property 1: Valid tenant data always creates a tenant."""
        # Ensure slug is unique for this test
        slug = f"{slug}-{Tenant.objects.count()}"
        
        tenant = Tenant.objects.create(name=name, slug=slug)
        
        assert tenant.pk is not None
        assert tenant.name == name
        assert tenant.slug == slug
        assert tenant.is_active is True
        
        # Cleanup
        tenant.delete()
    
    @hypothesis_settings
    @given(slug=slug_strategy)
    def test_tenant_slug_uniqueness(self, slug):
        """Property 2: Two tenants cannot have the same slug."""
        slug = f"unique-{slug}-{Tenant.objects.count()}"
        
        tenant1 = Tenant.objects.create(name="First", slug=slug)
        
        with pytest.raises((IntegrityError, ValidationError)):
            with transaction.atomic():
                Tenant.objects.create(name="Second", slug=slug)
        
        tenant1.delete()
    
    @hypothesis_settings
    @given(domain=domain_strategy)
    def test_tenant_domain_uniqueness(self, domain):
        """Property 3: Two tenants cannot have the same domain."""
        domain = f"unique{Tenant.objects.count()}.{domain.split('.')[-1]}"
        slug1 = f"tenant1-{Tenant.objects.count()}"
        slug2 = f"tenant2-{Tenant.objects.count() + 1}"
        
        tenant1 = Tenant.objects.create(name="First", slug=slug1, domain=domain)
        
        with pytest.raises((IntegrityError, ValidationError)):
            with transaction.atomic():
                Tenant.objects.create(name="Second", slug=slug2, domain=domain)
        
        tenant1.delete()
    
    @hypothesis_settings
    @given(slug=slug_strategy)
    def test_tenant_query_retrieval(self, slug):
        """Property 4: Created tenant can always be retrieved by slug."""
        slug = f"query-{slug}-{Tenant.objects.count()}"
        
        tenant = Tenant.objects.create(name="Test", slug=slug)
        
        retrieved = Tenant.objects.get(slug=slug)
        assert retrieved.pk == tenant.pk
        assert retrieved.name == tenant.name
        
        tenant.delete()


@pytest.mark.django_db(transaction=True)
class TestTenantMembershipProperties:
    """Property-based tests for TenantMembership model."""
    
    @hypothesis_settings
    @given(username=username_strategy)
    def test_membership_creation(self, username):
        """Property 5: Valid user-tenant pair creates membership."""
        username = f"{username}{User.objects.count()}"
        
        user = User.objects.create_user(username=username, password="test123")
        tenant = Tenant.objects.create(
            name="Test",
            slug=f"test-{TenantMembership.objects.count()}"
        )
        
        membership = TenantMembership.objects.create(user=user, tenant=tenant)
        
        assert membership.pk is not None
        assert membership.user == user
        assert membership.tenant == tenant
        assert membership.is_active is True
        
        membership.delete()
        tenant.delete()
        user.delete()
    
    @hypothesis_settings
    @given(username=username_strategy)
    def test_membership_uniqueness(self, username):
        """Property 6: User can have only one membership per tenant."""
        username = f"unique{username}{User.objects.count()}"
        
        user = User.objects.create_user(username=username, password="test123")
        tenant = Tenant.objects.create(
            name="Test",
            slug=f"unique-{TenantMembership.objects.count()}"
        )
        
        TenantMembership.objects.create(user=user, tenant=tenant)
        
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                TenantMembership.objects.create(user=user, tenant=tenant)
        
        user.delete()
        tenant.delete()
    
    @hypothesis_settings
    @given(num_tenants=st.integers(min_value=1, max_value=5))
    def test_user_can_belong_to_multiple_tenants(self, num_tenants):
        """Property 7: User can be member of multiple different tenants."""
        username = f"multi{User.objects.count()}"
        user = User.objects.create_user(username=username, password="test123")
        
        tenants = []
        memberships = []
        
        for i in range(num_tenants):
            tenant = Tenant.objects.create(
                name=f"Tenant {i}",
                slug=f"multi-tenant-{Tenant.objects.count()}-{i}"
            )
            tenants.append(tenant)
            membership = TenantMembership.objects.create(user=user, tenant=tenant)
            memberships.append(membership)
        
        # Verify user has all memberships
        user_tenants = Tenant.objects.filter(memberships__user=user)
        assert user_tenants.count() == num_tenants
        
        # Cleanup
        for m in memberships:
            m.delete()
        for t in tenants:
            t.delete()
        user.delete()


@pytest.mark.django_db(transaction=True)
class TestRoleProperties:
    """Property-based tests for Role model."""
    
    @hypothesis_settings
    @given(name=role_name_strategy)
    def test_role_creation(self, name):
        """Property 8: Valid role data creates a role."""
        tenant = Tenant.objects.create(
            name="Test",
            slug=f"role-test-{Role.objects.count()}"
        )
        name = f"{name[:40]}-{Role.objects.count()}"
        
        role = Role.objects.create(tenant=tenant, name=name)
        
        assert role.pk is not None
        assert role.tenant == tenant
        assert role.name == name
        
        role.delete()
        tenant.delete()
    
    @hypothesis_settings
    @given(name=role_name_strategy)
    def test_role_name_unique_within_tenant(self, name):
        """Property 9: Role names must be unique within a tenant."""
        tenant = Tenant.objects.create(
            name="Test",
            slug=f"role-unique-{Role.objects.count()}"
        )
        name = f"{name[:40]}-{Role.objects.count()}"
        
        Role.objects.create(tenant=tenant, name=name)
        
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Role.objects.create(tenant=tenant, name=name)
        
        tenant.delete()
    
    @hypothesis_settings
    @given(name=role_name_strategy)
    def test_same_role_name_different_tenants(self, name):
        """Property 10: Same role name can exist in different tenants."""
        base = Role.objects.count()
        tenant1 = Tenant.objects.create(name="T1", slug=f"role-t1-{base}")
        tenant2 = Tenant.objects.create(name="T2", slug=f"role-t2-{base}")
        name = f"{name[:40]}-{base}"
        
        role1 = Role.objects.create(tenant=tenant1, name=name)
        role2 = Role.objects.create(tenant=tenant2, name=name)
        
        assert role1.pk != role2.pk
        assert role1.name == role2.name
        assert role1.tenant != role2.tenant
        
        tenant1.delete()
        tenant2.delete()


@pytest.mark.django_db(transaction=True)
class TestPermissionProperties:
    """Property-based tests for Permission model."""
    
    @hypothesis_settings
    @given(codename=permission_codename_strategy)
    def test_permission_creation(self, codename):
        """Property 11: Valid permission data creates a permission."""
        tenant = Tenant.objects.create(
            name="Test",
            slug=f"perm-test-{Permission.objects.count()}"
        )
        
        permission = Permission.objects.create(
            tenant=tenant,
            codename=codename,
            name=f"Can {codename}",
        )
        
        assert permission.pk is not None
        assert permission.tenant == tenant
        assert permission.codename == codename
        
        permission.delete()
        tenant.delete()
    
    @hypothesis_settings
    @given(codename=permission_codename_strategy)
    def test_permission_unique_within_tenant(self, codename):
        """Property 12: Permission codenames must be unique within tenant."""
        tenant = Tenant.objects.create(
            name="Test",
            slug=f"perm-unique-{Permission.objects.count()}"
        )
        
        Permission.objects.create(tenant=tenant, codename=codename, name="Test")
        
        with pytest.raises((IntegrityError, ValidationError)):
            with transaction.atomic():
                Permission.objects.create(tenant=tenant, codename=codename, name="Test2")
        
        tenant.delete()
    
    @hypothesis_settings
    @given(invalid_codename=st.text(min_size=1, max_size=20).filter(lambda s: "." not in s))
    def test_invalid_codename_rejected(self, invalid_codename):
        """Property 13: Invalid codenames are rejected."""
        assume(len(invalid_codename) > 0)
        assume(invalid_codename.strip() == invalid_codename)
        
        tenant = Tenant.objects.create(
            name="Test",
            slug=f"perm-invalid-{Permission.objects.count()}"
        )
        
        permission = Permission(
            tenant=tenant,
            codename=invalid_codename,
            name="Invalid",
        )
        
        with pytest.raises(ValidationError):
            permission.full_clean()
        
        tenant.delete()


@pytest.mark.django_db(transaction=True)
class TestPermissionCheckingProperties:
    """Property-based tests for permission checking logic."""
    
    @hypothesis_settings
    @given(codename=permission_codename_strategy)
    def test_granted_permission_returns_true(self, codename):
        """Property 14: User with granted permission returns True."""
        from tenant_authx.permissions import TenantUser
        
        base = f"{Permission.objects.count()}"
        
        user = User.objects.create_user(username=f"perm{base}", password="test")
        tenant = Tenant.objects.create(name="Test", slug=f"check-{base}")
        permission = Permission.objects.create(
            tenant=tenant, codename=codename, name="Test"
        )
        role = Role.objects.create(tenant=tenant, name=f"Role{base}")
        role.permissions.add(permission)
        membership = TenantMembership.objects.create(user=user, tenant=tenant)
        membership.roles.add(role)
        
        tenant_user = TenantUser(user=user, tenant=tenant)
        
        assert tenant_user.has_perm(codename) is True
        
        user.delete()
        tenant.delete()
    
    @hypothesis_settings
    @given(codename=permission_codename_strategy)
    def test_not_granted_permission_returns_false(self, codename):
        """Property 15: User without permission returns False."""
        from tenant_authx.permissions import TenantUser
        
        base = f"{Permission.objects.count()}"
        
        user = User.objects.create_user(username=f"noperm{base}", password="test")
        tenant = Tenant.objects.create(name="Test", slug=f"nocheck-{base}")
        # Create permission but don't assign it
        Permission.objects.create(tenant=tenant, codename=codename, name="Test")
        TenantMembership.objects.create(user=user, tenant=tenant)
        
        tenant_user = TenantUser(user=user, tenant=tenant)
        
        assert tenant_user.has_perm(codename) is False
        
        user.delete()
        tenant.delete()
    
    @hypothesis_settings
    @given(codename=permission_codename_strategy)
    def test_superuser_bypass(self, codename):
        """Property 16: Superuser always has all permissions."""
        from tenant_authx.permissions import TenantUser
        
        base = f"{Permission.objects.count()}"
        
        superuser = User.objects.create_superuser(
            username=f"super{base}",
            password="test",
            email=f"super{base}@test.com"
        )
        tenant = Tenant.objects.create(name="Test", slug=f"super-{base}")
        
        tenant_user = TenantUser(user=superuser, tenant=tenant)
        
        # Superuser has any permission even without membership
        assert tenant_user.has_perm(codename) is True
        
        superuser.delete()
        tenant.delete()
    
    @hypothesis_settings
    @given(codename=permission_codename_strategy)
    def test_non_member_denied(self, codename):
        """Property 17: Non-member always denied permissions."""
        from tenant_authx.permissions import TenantUser
        
        base = f"{Permission.objects.count()}"
        
        user = User.objects.create_user(username=f"nonmem{base}", password="test")
        tenant = Tenant.objects.create(name="Test", slug=f"nonmem-{base}")
        # No membership created
        
        tenant_user = TenantUser(user=user, tenant=tenant)
        
        assert tenant_user.is_member() is False
        assert tenant_user.has_perm(codename) is False
        
        user.delete()
        tenant.delete()


@pytest.mark.django_db(transaction=True)
class TestTenantIsolationProperties:
    """Property-based tests for tenant isolation."""
    
    @hypothesis_settings
    @given(codename=permission_codename_strategy)
    def test_permission_isolated_to_tenant(self, codename):
        """Property 18: Permissions in one tenant don't apply to another."""
        from tenant_authx.permissions import TenantUser
        
        base = f"{Permission.objects.count()}"
        
        user = User.objects.create_user(username=f"iso{base}", password="test")
        tenant1 = Tenant.objects.create(name="T1", slug=f"iso1-{base}")
        tenant2 = Tenant.objects.create(name="T2", slug=f"iso2-{base}")
        
        # Create permission and role in tenant1
        perm = Permission.objects.create(tenant=tenant1, codename=codename, name="Test")
        role = Role.objects.create(tenant=tenant1, name=f"Role{base}")
        role.permissions.add(perm)
        m1 = TenantMembership.objects.create(user=user, tenant=tenant1)
        m1.roles.add(role)
        
        # User also member of tenant2 but no permissions there
        TenantMembership.objects.create(user=user, tenant=tenant2)
        
        tu1 = TenantUser(user=user, tenant=tenant1)
        tu2 = TenantUser(user=user, tenant=tenant2)
        
        assert tu1.has_perm(codename) is True
        assert tu2.has_perm(codename) is False  # Isolated!
        
        user.delete()
        tenant1.delete()
        tenant2.delete()
