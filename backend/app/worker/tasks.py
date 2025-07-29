from .celery_app import celery_app
from app.db.session import SessionLocal
from app.models.post import Post, PostStatus
from app.models.social_account import SocialAccount
from sqlalchemy.orm import Session
import httpx
from datetime import datetime, timedelta

@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def publish_to_linkedin(self, post_id: int):
    """
    Celery task to publish a post to LinkedIn using the UGC Posts API.
    """
    db: Session = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            print(f"[CELERY WORKER] Post {post_id} not found.")
            return

        social_account = db.query(SocialAccount).filter_by(
            user_id=post.user_id, provider='linkedin'
        ).first()

        if not social_account:
            post.status = PostStatus.FAILED
            db.commit()
            print(f"[CELERY WORKER] No LinkedIn account for user {post.user_id}. Failing post {post.id}.")
            return

        if social_account.expires_at and social_account.expires_at < datetime.utcnow() + timedelta(minutes=5):
            post.status = PostStatus.FAILED
            db.commit()
            print(f"[CELERY WORKER] LinkedIn token for user {post.user_id} is expired. Post {post.id} failed.")
            return f"Post {post_id} failed: LinkedIn token expired."

        api_url = "https://api.linkedin.com/v2/ugcPosts"
        headers = {
            "Authorization": f"Bearer {social_account.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
            # --- THIS HEADER IS THE FIX ---
            # LinkedIn's newer APIs require a version header.
            "LinkedIn-Version": "202309" 
        }
        
        post_body = {
            "author": social_account.provider_user_id,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": post.content
                    },
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "CONNECTIONS"
            }
        }

        with httpx.Client() as client:
            print(f"[CELERY WORKER] Posting to LinkedIn for post ID: {post.id}")
            print(f"[CELERY WORKER] Using author URN: {social_account.provider_user_id}")
            response = client.post(api_url, headers=headers, json=post_body)
            print(f"[CELERY WORKER] LinkedIn API response status: {response.status_code}")
            print(f"[CELERY WORKER] LinkedIn API response body: {response.text}")
            response.raise_for_status()
        
        print(f"[CELERY WORKER] Successfully published Post ID {post.id} to LinkedIn.")
        post.status = PostStatus.PUBLISHED
        db.commit()
        return f"Post {post_id} published to LinkedIn."

    except httpx.HTTPStatusError as exc:
        print(f"[CELERY WORKER] HTTP error for post {post_id}: {exc.response.text}")
        post.status = PostStatus.FAILED
        db.commit()
        if 500 <= exc.response.status_code <= 599 or exc.response.status_code == 429:
            raise self.retry(exc=exc)
    except Exception as exc:
        print(f"[CELERY WORKER] Unexpected error for post {post_id}: {exc}")
        post.status = PostStatus.FAILED
        db.commit()
        raise self.retry(exc=exc)
    finally:
        db.close()