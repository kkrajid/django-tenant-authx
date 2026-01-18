"""
Tests for tenant_authx DRF integration.
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from tenant_authx.models import Tenant, TenantMembership, Role, Permission
from tenant_authx.drf.permissions import (
    IsTenantMember,
    TenantPermission,
    HasTenantPermission,
    TenantObjectPermission,
    TenantAdminPermission,
)
from tenant_authx.drf.authentication import (
    TenantSessionAuthentication,
    TenantAuthenticationMixin,
)
from tenant_authx.permissions import TenantUser


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
        slug="test-tenant-drf",
    )


@pytest.fixture
def permission(db, tenant):
    """Create a test permission."""
    return Permission.objects.create(
        tenant=tenant,
        codename="api.view_resource",
        name="Can view resources",
    )


@pytest.fixture
def role(db, tenant, permission):
    """Create a test role with permissions."""
    role = Role.objects.create(
        tenant=tenant,
        name="APIUser",
    )
    role.permissions.add(permission)
    return role


@pytest.fixture
def admin_role(db, tenant):
    """Create admin role."""
    return Role.objects.create(
        tenant=tenant,
        name="Admin",
    )


@pytest.fixture
def membership(db, user, tenant, role):
    """Create a test membership with roles."""
    membership = TenantMembership.objects.create(
        user=user,
        tenant=tenant,
    )
    membership.roles.add(role)
    return membership


@pytest.fixture
def request_factory():
    """Create API request factory."""
    return APIRequestFactory()


class DummyView(APIView):
    """Dummy view for testing permissions."""
    
    def get(self, request):
        return Response({"status": "ok"})


class TestIsTenantMember:
    """Tests for IsTenantMember permission class."""
    
    def test_authenticated_member_allowed(self, user, tenant, membership, request_factory):
        """Test that authenticated tenant members are allowed."""
        request = request_factory.get("/test/")
        request.user = user
        request.tenant = tenant
        request.tenant_user = TenantUser(user=user, tenant=tenant)
        
        permission = IsTenantMember()
        view = DummyView()
        
        assert permission.has_permission(request, view) is True
    
    def test_authenticated_non_member_denied(self, user, tenant, request_factory):
        """Test that authenticated non-members are denied."""
        # No membership created
        request = request_factory.get("/test/")
        request.user = user
        request.tenant = tenant
        request.tenant_user = TenantUser(user=user, tenant=tenant)
        
        permission = IsTenantMember()
        view = DummyView()
        
        assert permission.has_permission(request, view) is False
    
    def test_unauthenticated_denied(self, tenant, request_factory):
        """Test that unauthenticated users are denied."""
        from django.contrib.auth.models import AnonymousUser
        
        request = request_factory.get("/test/")
        request.user = AnonymousUser()
        request.tenant = tenant
        request.tenant_user = None
        
        permission = IsTenantMember()
        view = DummyView()
        
        assert permission.has_permission(request, view) is False
    
    def test_no_tenant_denied(self, user, request_factory):
        """Test that requests without tenant are denied."""
        request = request_factory.get("/test/")
        request.user = user
        request.tenant = None
        
        permission = IsTenantMember()
        view = DummyView()
        
        assert permission.has_permission(request, view) is False
    
    def test_superuser_allowed_without_membership(self, superuser, tenant, request_factory):
        """Test that superusers are allowed even without membership."""
        request = request_factory.get("/test/")
        request.user = superuser
        request.tenant = tenant
        request.tenant_user = TenantUser(user=superuser, tenant=tenant)
        
        permission = IsTenantMember()
        view = DummyView()
        
        assert permission.has_permission(request, view) is True


class TestHasTenantPermission:
    """Tests for HasTenantPermission class."""
    
    def test_has_permission_granted(self, user, tenant, membership, permission, request_factory):
        """Test permission is granted when user has it."""
        request = request_factory.get("/test/")
        request.user = user
        request.tenant = tenant
        request.tenant_user = TenantUser(user=user, tenant=tenant)
        
        class ViewWithPerm(DummyView):
            required_permissions = ["api.view_resource"]
        
        perm_class = HasTenantPermission()
        view = ViewWithPerm()
        
        assert perm_class.has_permission(request, view) is True
    
    def test_has_permission_denied(self, user, tenant, membership, request_factory):
        """Test permission is denied when user lacks it."""
        request = request_factory.get("/test/")
        request.user = user
        request.tenant = tenant
        request.tenant_user = TenantUser(user=user, tenant=tenant)
        
        class ViewWithPerm(DummyView):
            required_permissions = ["api.delete_resource"]  # Not assigned
        
        perm_class = HasTenantPermission()
        view = ViewWithPerm()
        
        assert perm_class.has_permission(request, view) is False
    
    def test_no_permissions_required(self, user, tenant, membership, request_factory):
        """Test no permissions required just checks membership."""
        request = request_factory.get("/test/")
        request.user = user
        request.tenant = tenant
        request.tenant_user = TenantUser(user=user, tenant=tenant)
        
        perm_class = HasTenantPermission()
        view = DummyView()  # No required_permissions
        
        assert perm_class.has_permission(request, view) is True


class TestTenantAdminPermission:
    """Tests for TenantAdminPermission class."""
    
    def test_admin_allowed(self, user, tenant, admin_role, request_factory, db):
        """Test admin role is allowed."""
        membership = TenantMembership.objects.create(user=user, tenant=tenant)
        membership.roles.add(admin_role)
        
        request = request_factory.get("/test/")
        request.user = user
        request.tenant = tenant
        request.tenant_user = TenantUser(user=user, tenant=tenant)
        
        permission = TenantAdminPermission()
        view = DummyView()
        
        assert permission.has_permission(request, view) is True
    
    def test_non_admin_denied(self, user, tenant, role, membership, request_factory):
        """Test non-admin role is denied."""
        # User has 'APIUser' role, not 'Admin'
        request = request_factory.get("/test/")
        request.user = user
        request.tenant = tenant
        request.tenant_user = TenantUser(user=user, tenant=tenant)
        
        permission = TenantAdminPermission()
        view = DummyView()
        
        assert permission.has_permission(request, view) is False


class TestTenantObjectPermission:
    """Tests for TenantObjectPermission class."""
    
    def test_object_in_same_tenant_allowed(self, user, tenant, membership, request_factory):
        """Test access to object in same tenant is allowed."""
        request = request_factory.get("/test/")
        request.user = user
        request.tenant = tenant
        request.tenant_user = TenantUser(user=user, tenant=tenant)
        
        # Create a mock object with tenant attribute
        class MockObject:
            pk = tenant.pk
        
        obj = MockObject()
        obj.tenant = tenant
        
        permission = TenantObjectPermission()
        view = DummyView()
        
        assert permission.has_object_permission(request, view, obj) is True
    
    def test_object_in_different_tenant_denied(self, user, tenant, membership, request_factory, db):
        """Test access to object in different tenant is denied."""
        other_tenant = Tenant.objects.create(name="Other", slug="other-drf-test")
        
        request = request_factory.get("/test/")
        request.user = user
        request.tenant = tenant
        request.tenant_user = TenantUser(user=user, tenant=tenant)
        
        class MockObject:
            pass
        
        obj = MockObject()
        obj.tenant = other_tenant
        obj.pk = other_tenant.pk
        
        permission = TenantObjectPermission()
        view = DummyView()
        
        assert permission.has_object_permission(request, view, obj) is False
