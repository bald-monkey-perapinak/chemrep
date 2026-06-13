"""
Tests for students API: CRUD operations.
"""
import pytest


@pytest.mark.asyncio
async def test_create_student(client, auth_token):
    response = await client.post(
        "/api/v1/students",
        json={"full_name": "Test Student", "email": "student@example.com", "grade": 10},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["full_name"] == "Test Student"
    assert data["email"] == "student@example.com"
    assert data["grade"] == 10
    assert "id" in data


@pytest.mark.asyncio
async def test_list_students(client, auth_token):
    await client.post(
        "/api/v1/students",
        json={"full_name": "List Student"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    response = await client.get(
        "/api/v1/students",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert any(s["full_name"] == "List Student" for s in data)


@pytest.mark.asyncio
async def test_delete_student(client, auth_token):
    create_response = await client.post(
        "/api/v1/students",
        json={"full_name": "Delete Student"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    student_id = create_response.json()["id"]

    response = await client.delete(
        f"/api/v1/students/{student_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 204

    get_response = await client.get(
        f"/api/v1/students/{student_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_create_student_unauthorized(client):
    response = await client.post(
        "/api/v1/students",
        json={"full_name": "Unauthorized Student"},
    )
    assert response.status_code == 401
