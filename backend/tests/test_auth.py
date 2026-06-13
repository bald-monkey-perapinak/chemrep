"""
Tests for auth API: password hashing, JWT tokens, login, me.
"""
import pytest


class TestPasswordHashing:
    def test_hash_password(self):
        from src.api.routes.auth import _hash

        hashed = _hash("testpassword123")
        assert hashed != "testpassword123"
        assert len(hashed) > 0

    def test_verify_correct_password(self):
        from src.api.routes.auth import _hash, _verify

        password = "testpassword123"
        hashed = _hash(password)
        assert _verify(password, hashed) is True

    def test_verify_wrong_password(self):
        from src.api.routes.auth import _hash, _verify

        hashed = _hash("testpassword123")
        assert _verify("wrongpassword", hashed) is False


class TestJWTToken:
    def test_make_token(self):
        from src.api.routes.auth import _make_token

        token = _make_token("test-teacher-id")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_token(self):
        from src.api.routes.auth import SECRET_KEY, ALGORITHM, _make_token
        from jose import jwt

        teacher_id = "test-teacher-id"
        token = _make_token(teacher_id)
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == teacher_id

    def test_token_contains_expiry(self):
        from src.api.routes.auth import SECRET_KEY, ALGORITHM, _make_token
        from jose import jwt

        token = _make_token("test-teacher-id")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert "exp" in payload


@pytest.mark.asyncio
async def test_register(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "newteacher@example.com",
            "password": "password123",
            "full_name": "New Teacher",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newteacher@example.com"
    assert data["full_name"] == "New Teacher"
    assert "id" in data


@pytest.mark.asyncio
async def test_login(client, test_teacher):
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "teacher@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client, test_teacher):
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "teacher@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me(client, auth_token):
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "teacher@example.com"
    assert data["full_name"] == "Test Teacher"


@pytest.mark.asyncio
async def test_me_no_token(client):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
