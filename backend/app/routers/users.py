from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_password_set
from app.models.user import User
from app.schemas.user_list import UserListItem

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserListItem])
async def list_users(
    db: AsyncSession = Depends(get_db), _: User = Depends(require_password_set)
) -> list[User]:
    return list(await db.scalars(select(User).order_by(User.display_name)))
