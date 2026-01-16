"""
Tests for tag management endpoints.
"""
from fastapi.testclient import TestClient


class TestTagsRead:
    """Test tag reading."""
    
    def test_get_tags_authenticated(self, auth_client: TestClient):
        """Test getting tags while authenticated."""
        response = auth_client.get("/tags")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_get_tags_unauthenticated(self, client: TestClient):
        """Test that unauthenticated users cannot access tags."""
        response = client.get("/tags")
        assert response.status_code == 401


class TestTagsCRUD:
    """Test tag create, update, delete (admin only)."""
    
    def test_create_tag_as_admin(self, admin_client: TestClient):
        """Test creating a tag as admin."""
        response = admin_client.post(
            "/tags",
            json={
                "name": "Important",
                "color": "#ff0000"
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Important"
        assert data["color"] == "#ff0000"
    
    def test_create_tag_as_regular_user(self, auth_client: TestClient):
        """Test that regular users cannot create tags."""
        response = auth_client.post(
            "/tags",
            json={
                "name": "Test",
                "color": "#00ff00"
            }
        )
        assert response.status_code == 403
    
    def test_create_tag_invalid_color(self, admin_client: TestClient):
        """Test tag creation with invalid color format."""
        response = admin_client.post(
            "/tags",
            json={
                "name": "Test",
                "color": "not-a-color"
            }
        )
        assert response.status_code == 422
    
    def test_create_tag_empty_name(self, admin_client: TestClient):
        """Test tag creation with empty name."""
        response = admin_client.post(
            "/tags",
            json={
                "name": "",
                "color": "#ff0000"
            }
        )
        assert response.status_code == 422
    
    def test_delete_tag_as_admin(self, admin_client: TestClient, session):
        """Test deleting a tag as admin."""
        # First create a tag
        from models import Tag
        tag = Tag(name="ToDelete", color="#cccccc")
        session.add(tag)
        session.commit()
        session.refresh(tag)
        
        # Then delete it
        response = admin_client.delete(f"/tags/{tag.id}")
        assert response.status_code == 204
    
    def test_delete_tag_nonexistent(self, admin_client: TestClient):
        """Test deleting a tag that doesn't exist."""
        response = admin_client.delete("/tags/99999")
        assert response.status_code == 404
    
    def test_update_tag_as_admin(self, admin_client: TestClient, session):
        """Test updating a tag as admin."""
        from models import Tag
        tag = Tag(name="Original", color="#000000")
        session.add(tag)
        session.commit()
        session.refresh(tag)
        
        response = admin_client.put(
            f"/tags/{tag.id}",
            json={"name": "Updated", "color": "#ffffff"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated"
        assert data["color"] == "#ffffff"
