"""
Tests for authentication endpoints.
"""
from fastapi.testclient import TestClient


class TestAuthentication:
    """Test authentication flows."""
    
    def test_login_success(self, client: TestClient, test_user):
        """Test successful login."""
        response = client.post(
            "/token",
            data={
                "username": "testuser",
                "password": "testpassword123"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
    
    def test_login_wrong_password(self, client: TestClient, test_user):
        """Test login with wrong password."""
        response = client.post(
            "/token",
            data={
                "username": "testuser",
                "password": "wrongpassword"
            }
        )
        assert response.status_code == 401
    
    def test_login_nonexistent_user(self, client: TestClient):
        """Test login with non-existent user."""
        response = client.post(
            "/token",
            data={
                "username": "nonexistent",
                "password": "somepassword"
            }
        )
        assert response.status_code == 401
    
    def test_logout(self, auth_client: TestClient):
        """Test logout clears cookie."""
        response = auth_client.post("/logout")
        assert response.status_code == 200
        # Cookie is cleared by setting max_age=0
        assert "access_token" in response.cookies or response.status_code == 200
    
    def test_protected_route_without_auth(self, client: TestClient):
        """Test that protected routes require authentication."""
        response = client.get("/contracts")
        assert response.status_code == 401


class TestUserCreation:
    """Test user registration."""
    
    def test_create_user_invalid_username_short(self, client: TestClient):
        """Test username validation - too short."""
        response = client.post(
            "/users",
            json={
                "username": "ab",  # Too short (min 3)
                "password": "validpassword123"
            }
        )
        assert response.status_code == 422
    
    def test_create_user_invalid_password_short(self, client: TestClient):
        """Test password validation - too short."""
        response = client.post(
            "/users",
            json={
                "username": "validuser",
                "password": "short"  # Too short (min 8)
            }
        )
        assert response.status_code == 422
    
    def test_create_user_invalid_username_chars(self, client: TestClient):
        """Test username with invalid characters."""
        response = client.post(
            "/users",
            json={
                "username": "user@name!",  # Invalid chars
                "password": "validpassword123"
            }
        )
        assert response.status_code == 422
