"""
Tests for contract CRUD endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from io import BytesIO


class TestContractList:
    """Test contract listing."""
    
    def test_get_contracts_empty(self, auth_client: TestClient):
        """Test getting contracts when none exist."""
        response = auth_client.get("/contracts")
        assert response.status_code == 200
        assert response.json() == []
    
    def test_get_contracts_unauthenticated(self, client: TestClient):
        """Test that unauthenticated users cannot access contracts."""
        response = client.get("/contracts")
        assert response.status_code == 401


class TestContractSearch:
    """Test contract search and filtering."""
    
    def test_search_query_parameter(self, auth_client: TestClient):
        """Test search query parameter is accepted."""
        response = auth_client.get("/contracts?search=test")
        assert response.status_code == 200
    
    def test_filter_by_tag(self, auth_client: TestClient):
        """Test filtering by tag."""
        response = auth_client.get("/contracts?tags=important")
        assert response.status_code == 200
    
    def test_sort_options(self, auth_client: TestClient):
        """Test sort options."""
        # Test valid sort options
        for sort_by in ["title", "value", "start_date", "end_date", "uploaded_at"]:
            response = auth_client.get(f"/contracts?sort_by={sort_by}")
            assert response.status_code == 200
        
        for sort_order in ["asc", "desc"]:
            response = auth_client.get(f"/contracts?sort_order={sort_order}")
            assert response.status_code == 200


class TestContractCRUD:
    """Test contract create, read, update, delete."""
    
    def test_create_contract_missing_file(self, auth_client: TestClient):
        """Test creating contract without file fails."""
        response = auth_client.post(
            "/contracts",
            data={
                "title": "Test Contract",
                "start_date": "2024-01-01T00:00:00",
                "end_date": "2024-12-31T23:59:59",
                "value": 1000.0
            }
        )
        assert response.status_code == 422
    
    def test_get_nonexistent_contract(self, auth_client: TestClient):
        """Test getting a contract that doesn't exist."""
        response = auth_client.get("/contracts/99999/download")
        assert response.status_code == 404
    
    def test_delete_nonexistent_contract(self, auth_client: TestClient):
        """Test deleting a contract that doesn't exist."""
        response = auth_client.delete("/contracts/99999")
        assert response.status_code == 404
    
    def test_update_nonexistent_contract(self, auth_client: TestClient):
        """Test updating a contract that doesn't exist."""
        response = auth_client.put(
            "/contracts/99999",
            data={"title": "Updated Title"}
        )
        assert response.status_code == 404
