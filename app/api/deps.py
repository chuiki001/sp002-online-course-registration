from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.domain import User
from app.repositories.registration_repo import RegistrationRepository

bearer_scheme = HTTPBearer(auto_error=False)


def get_repo(db: Session = Depends(get_db)) -> RegistrationRepository:
    return RegistrationRepository(db)


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    repo: RegistrationRepository = Depends(get_repo),
) -> User:
    if not creds or not creds.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authentication token.")
    try:
        payload = decode_access_token(creds.credentials)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token.")

    user = repo.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    return user


def require_role(*allowed_roles: str):
    def _guard(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' is not authorized for this resource.",
            )
        return current_user

    return _guard
