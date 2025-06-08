import datetime
from unittest import mock

from fastapi.testclient import TestClient

from api.core.security import create_access_token, create_refresh_token
from api.schemas.user import UserProfile


@mock.patch("api.core.security.settings.SECRET_KEY", "test-key")
def test_get_me_with_access_token(client: TestClient):
    user = UserProfile(
        id="user123",
        email="user@example.com",
        display_name="User",
        avatar_url=None,
        bio=None,
        lang="en-US",
        followers_count=0,
        following_count=0,
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow(),
        is_active=True,
        is_verified=True,
        is_admin=False,
    )

    async def mock_get_by_id(self, uid: str):
        return user

    with mock.patch("api.services.user.UserService.get_by_id", mock_get_by_id):
        token = create_access_token(user.id)
        response = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user.id
    assert data["email"] == user.email
    assert data["display_name"] == user.display_name


@mock.patch("api.core.security.settings.SECRET_KEY", "test-key")
def test_get_me_with_refresh_token(client: TestClient):
    user = UserProfile(
        id="user123",
        email="user@example.com",
        display_name="User",
        avatar_url=None,
        bio=None,
        lang="en-US",
        followers_count=0,
        following_count=0,
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow(),
        is_active=True,
        is_verified=True,
        is_admin=False,
    )

    async def mock_get_by_id(self, uid: str):
        return user

    with mock.patch("api.services.user.UserService.get_by_id", mock_get_by_id):
        token = create_refresh_token(user.id)
        response = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )

    assert response.status_code == 401
    assert "Cannot use refresh token" in response.json()["detail"]
