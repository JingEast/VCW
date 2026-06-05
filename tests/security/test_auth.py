"""Authentication and authorization tests for SEC-07/08/09."""
import pytest


@pytest.fixture
def auth_client(client):
    """Return test client with auth utilities."""
    return client


class TestApiAuth:
    """API authentication via JWT."""

    def test_api_login_invalid_credentials(self, auth_client):
        r = auth_client.post("/api/v1/auth/login", json={"username": "nope", "password": "nope"})
        assert r.status_code == 401
        assert r.get_json()["success"] is False

    def test_api_register_and_login(self, auth_client):
        # Register
        r = auth_client.post("/api/v1/auth/register", json={
            "username": "apitest",
            "email": "apitest@example.com",
            "password": "password123",
        })
        assert r.status_code == 201
        assert r.get_json()["success"] is True

        # Login
        r = auth_client.post("/api/v1/auth/login", json={
            "username": "apitest",
            "password": "password123",
        })
        assert r.status_code == 200
        data = r.get_json()["data"]
        assert "access_token" in data
        assert "refresh_token" in data

    def test_api_me_unauthenticated(self, auth_client):
        r = auth_client.get("/api/v1/auth/me")
        assert r.status_code == 401

    def test_api_me_with_jwt(self, auth_client):
        # Register + login
        auth_client.post("/api/v1/auth/register", json={
            "username": "jwtme",
            "email": "jwtme@example.com",
            "password": "password123",
        })
        r = auth_client.post("/api/v1/auth/login", json={
            "username": "jwtme",
            "password": "password123",
        })
        token = r.get_json()["data"]["access_token"]

        r = auth_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.get_json()["data"]["user"]["username"] == "jwtme"


class TestPageAuth:
    """Session authentication via page routes."""

    def test_login_page_loads(self, auth_client):
        r = auth_client.get("/login")
        assert r.status_code == 200
        assert b"csrf_token" in r.data

    def test_register_page_loads(self, auth_client):
        r = auth_client.get("/register")
        assert r.status_code == 200
        assert b"csrf_token" in r.data

    def test_page_register_and_login(self, auth_client):
        import re

        # Get CSRF token from register page
        r = auth_client.get("/register")
        m = re.search(r'name="csrf_token" value="([^"]+)"', r.data.decode())
        csrf = m.group(1) if m else ""

        # Register
        r = auth_client.post("/register", data={
            "username": "pagetest",
            "email": "pagetest@example.com",
            "password": "password123",
            "password_confirm": "password123",
            "csrf_token": csrf,
        })
        assert r.status_code == 302  # redirect to login

        # Get CSRF token from login page
        r = auth_client.get("/login")
        m = re.search(r'name="csrf_token" value="([^"]+)"', r.data.decode())
        csrf = m.group(1) if m else ""

        # Login
        r = auth_client.post("/login", data={
            "username": "pagetest",
            "password": "password123",
            "csrf_token": csrf,
        })
        assert r.status_code == 302  # redirect after login

    def test_logout_requires_login(self, auth_client):
        r = auth_client.get("/logout")
        assert r.status_code == 302  # @login_required redirects to login page


class TestCsrfInTemplates:
    """CSRF tokens are present in all POST forms."""

    @pytest.mark.parametrize("path", [
        "/", "/batch", "/config", "/editor", "/memory", "/trends",
    ])
    def test_csrf_token_in_form(self, auth_client, path):
        r = auth_client.get(path)
        assert r.status_code == 200
        assert b'csrf_token' in r.data
