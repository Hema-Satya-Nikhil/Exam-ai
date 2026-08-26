from app.schemas.auth import UserContext
from app.services.auth_service import AuthService


def test_access_token_round_trip() -> None:
    service = AuthService()
    user = UserContext(
        user_id="user-1",
        email="faculty@example.edu",
        full_name="Faculty User",
        roles=["faculty"],
        is_active=True,
    )

    token = service.create_access_token(user, expires_in_seconds=60)
    parsed = service.verify_access_token(token)

    assert parsed is not None
    assert parsed.email == user.email
    assert parsed.roles == user.roles
