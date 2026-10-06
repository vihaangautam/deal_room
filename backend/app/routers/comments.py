import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_password_set
from app.models.comment import Comment
from app.models.user import User
from app.schemas.comment import CommentCreate, CommentRead, CommentUpdate

router = APIRouter(tags=["comments"])

EDIT_WINDOW = timedelta(minutes=15)  # PRD F8


def _read(comment: Comment, author_name: str) -> CommentRead:
    return CommentRead(
        id=comment.id,
        parent_id=comment.parent_id,
        author_id=comment.author_id,
        author_name=author_name,
        body="Comment removed" if comment.deleted else comment.body,
        edited=comment.edited,
        deleted=comment.deleted,
        created_at=comment.created_at,
    )


async def _list(db: AsyncSession, deal_id: uuid.UUID, task_id: uuid.UUID | None) -> list[CommentRead]:
    rows = await db.execute(
        select(Comment, User.display_name)
        .join(User, User.id == Comment.author_id)
        .where(Comment.deal_id == deal_id, Comment.task_id == task_id)
        .order_by(Comment.created_at)
    )
    return [_read(c, name) for c, name in rows]


async def _create(
    db: AsyncSession, deal_id: uuid.UUID, task_id: uuid.UUID | None, body: CommentCreate, user: User
) -> CommentRead:
    if body.parent_id:
        parent = await db.get(Comment, body.parent_id)
        if parent is None or parent.deal_id != deal_id or parent.task_id != task_id:
            raise HTTPException(status_code=404, detail="Comment not found")
        if parent.parent_id is not None:
            # PRD F8: "one level of replies" — a reply to a reply isn't allowed.
            raise HTTPException(status_code=422, detail="Replies can only be one level deep")

    comment = Comment(
        deal_id=deal_id, task_id=task_id, parent_id=body.parent_id, author_id=user.id, body=body.body
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return _read(comment, user.display_name)


@router.get("/deals/{deal_id}/comments", response_model=list[CommentRead])
async def list_deal_comments(
    deal_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(require_password_set)
) -> list[CommentRead]:
    return await _list(db, deal_id, None)


@router.post("/deals/{deal_id}/comments", response_model=CommentRead, status_code=201)
async def create_deal_comment(
    deal_id: uuid.UUID,
    body: CommentCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_password_set),
) -> CommentRead:
    return await _create(db, deal_id, None, body, user)


@router.get("/deals/{deal_id}/tasks/{task_id}/comments", response_model=list[CommentRead])
async def list_task_comments(
    deal_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_password_set),
) -> list[CommentRead]:
    return await _list(db, deal_id, task_id)


@router.post("/deals/{deal_id}/tasks/{task_id}/comments", response_model=CommentRead, status_code=201)
async def create_task_comment(
    deal_id: uuid.UUID,
    task_id: uuid.UUID,
    body: CommentCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_password_set),
) -> CommentRead:
    return await _create(db, deal_id, task_id, body, user)


@router.patch("/comments/{comment_id}", response_model=CommentRead)
async def edit_comment(
    comment_id: uuid.UUID,
    body: CommentUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_password_set),
) -> CommentRead:
    comment = await db.get(Comment, comment_id)
    if comment is None or comment.deleted:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.author_id != user.id:
        raise HTTPException(status_code=403, detail="Only the author can edit this comment")
    if datetime.now(timezone.utc) - comment.created_at > EDIT_WINDOW:
        raise HTTPException(status_code=403, detail="This comment can no longer be edited")

    comment.body = body.body
    comment.edited = True
    await db.commit()
    return _read(comment, user.display_name)


@router.delete("/comments/{comment_id}", status_code=204)
async def delete_comment(
    comment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_password_set),
) -> None:
    comment = await db.get(Comment, comment_id)
    if comment is None or comment.deleted:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.author_id != user.id:
        raise HTTPException(status_code=403, detail="Only the author can delete this comment")

    comment.deleted = True
    await db.commit()
