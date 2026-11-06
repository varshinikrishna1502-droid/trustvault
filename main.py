from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import Base, SessionLocal, engine, get_db
from models import User
from security import current_user, hash_password, make_token, require_role, verify_password
from documents import admin_router, router as documents_router

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def seed():
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            for email, pw, role in [
                ("admin@trustvault.com", "Admin@12345", "admin"),
                ("owner@trustvault.com", "Owner@12345", "owner"),
                ("viewer@trustvault.com", "Viewer@12345", "viewer"),
            ]:
                db.add(User(email=email, password_hash=hash_password(pw), role=role))
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    seed()
    yield


app = FastAPI(
    title="TrustVault",
    description="Secure Document Sharing with Audit Trail",
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(documents_router)
app.include_router(admin_router)


class SignupIn(BaseModel):
    email: str = Field(min_length=5, max_length=100, pattern=EMAIL_PATTERN)
    password: str = Field(min_length=8, max_length=64)


class LoginIn(BaseModel):
    email: str
    password: str


class RoleIn(BaseModel):
    role: str = Field(pattern="^(admin|owner|viewer)$")


@app.get("/")
def home():
    return {"message": "Welcome to TrustVault", "status": "Backend is running"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.post("/auth/signup", status_code=201)
def signup(body: SignupIn, db: Session = Depends(get_db)):
    if db.query(User).filter_by(email=body.email.lower()).first():
        raise HTTPException(400, "Could not create account")
    # role is ALWAYS viewer here. The request body can never set it.
    user = User(email=body.email.lower(), password_hash=hash_password(body.password), role="viewer")
    db.add(user)
    db.commit()
    return {"id": user.id, "email": user.email, "role": user.role}


@app.post("/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=body.email.lower()).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Wrong email or password")
    return {"access_token": make_token(user), "token_type": "bearer"}


@app.get("/auth/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email, "role": user.role}


@app.put("/admin/users/{user_id}/role")
def change_role(user_id: int, body: RoleIn, db: Session = Depends(get_db),
                admin: User = Depends(require_role("admin"))):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "Not found")
    target.role = body.role
    target.token_version += 1  # old tokens stop working immediately
    db.commit()
    return {"id": target.id, "role": target.role}