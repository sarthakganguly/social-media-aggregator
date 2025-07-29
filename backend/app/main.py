from fastapi import FastAPI
from app.api.routes import auth, users, linkedin, posts
from app.db.session import engine
from app.models import user, social_account, post

# Create database tables on startup
# Base.metadata.create_all(bind=engine) will create all tables from imported models
user.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Social Media Aggregator - Backend API", version="1.0")

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(linkedin.router, prefix="/api/linkedin", tags=["linkedin"])
app.include_router(posts.router, prefix="/api/posts", tags=["posts"])

@app.get("/api/health")
def health_check():
    return {"status": "ok"}