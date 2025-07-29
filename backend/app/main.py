from fastapi import FastAPI
from app.api.routes import auth, users, linkedin
from app.db.session import engine
from app.models import user, social_account # Import social_account to ensure tables are created

# Create database tables on startup
user.Base.metadata.create_all(bind=engine)
social_account.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Social Media Aggregator - Backend API", version="1.0")

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(linkedin.router, prefix="/api/linkedin", tags=["linkedin"])

@app.get("/api/health")
def health_check():
    return {"status": "ok"}