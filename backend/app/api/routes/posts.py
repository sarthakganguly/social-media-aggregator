from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List

from app.db.session import get_db
from app.models.user import User
from app.models.post import Post, PostStatus
from app.schemas.post import PostCreate, PostInDB
from app.dependencies import get_current_user_required
from app.worker.tasks import publish_to_linkedin
from app.worker.tasks import publish_to_linkedin, publish_to_twitter


router = APIRouter()

@router.post("/", response_model=PostInDB, status_code=status.HTTP_201_CREATED)
def create_post(
    post_data: PostCreate,
    action: str, # 'post_now' or 'save_draft'
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """
    Creates a new post. If action is 'post_now', it triggers publishing tasks.
    If action is 'save_draft', it saves the post with a 'draft' status.
    """
    if action == "post_now":
        post_status = PostStatus.SCHEDULED # Marked as scheduled to be picked up by worker
        published_time = datetime.utcnow()
    elif action == "save_draft":
        post_status = PostStatus.DRAFT
        published_time = None
    else:
        raise HTTPException(status_code=400, detail="Invalid action specified.")

    new_post = Post(
        content=post_data.content,
        user_id=current_user.id,
        status=post_status,
        published_at=published_time
    )
    db.add(new_post)
    db.commit()
    db.refresh(new_post)

    # Trigger async tasks only if posting now and channels are selected
    if action == "post_now" and post_data.channels:
        if "linkedin" in post_data.channels:
            publish_to_linkedin.delay(new_post.id)
        if "twitter" in post_data.channels:
            publish_to_twitter.delay(new_post.id)

    return new_post

@router.get("/drafts", response_model=List[PostInDB])
def get_draft_posts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """
    Retrieves all posts with the status 'draft' for the current user.
    """
    drafts = db.query(Post).filter(Post.user_id == current_user.id, Post.status == PostStatus.DRAFT).order_by(Post.created_at.desc()).all()
    return drafts

@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """
    Deletes a specific post.
    """
    post_to_delete = db.query(Post).filter(Post.id == post_id).first()

    if not post_to_delete:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")
    
    if post_to_delete.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this post.")

    db.delete(post_to_delete)
    db.commit()
    return