import os
import json
import redis
from fastapi import FastAPI, HTTPException, Depends
from github_service import (
    fetch_open_issues,
    get_issues_batch,
    search_repos,
    GitHubError,
    RepoRequest,
)
from database import engine
from database import Base
from sqlalchemy.orm import Session
from database import get_db
from models import Preference, User, SentNotification
from pydantic import BaseModel
import bcrypt
import jwt
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from apscheduler.schedulers.background import BackgroundScheduler
from contextlib import asynccontextmanager
from database import engine, Base, get_db, SessionLocal
import smtplib
from email.message import EmailMessage

SMTP_EMAIL = os.environ.get("SMTP_EMAIL")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")

def notify(user_id: str, result: dict, db: Session):
    user = db.query(User).filter(User.username == user_id).first()
    if user is None or user.email is None:
        return

    new_issues = []
    for repo in result["results"]:
        for issue in repo["issues"]:
            url = issue["url"]

            already = db.query(SentNotification).filter(
                SentNotification.user_id == user.id,
                SentNotification.issue_url == url
            ).first()
            if already:
                continue
            new_issues.append(issue)
            db.add(SentNotification(user_id=user.id, issue_url=url))

    if not new_issues:
        return

    body = f"Found {len(new_issues)} new issues for your preference."
    try:
        send_email(user.email, "New issues found - Issue Scout", body)
    except Exception as e:
        print(f"Email failed for {user.username}: {e}")
        return

    db.commit()

def send_email(to_email: str, subject: str, body: str):
    msg = EmailMessage()
    msg["From"] = SMTP_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.send_message(msg)

def hourly_job():
    db = SessionLocal()
    try:
        preferences = db.query(Preference).all()
        for pref in preferences:
            try:
                result = run_discovery(pref.language, pref.min_stars)
                if result["results"]:
                    notify(pref.user_id, result, db)
            except Exception as e:
                print(f"Job failed for {pref.user_id}: {e}")
                continue
    finally:
        db.close()

scheduler = BackgroundScheduler()
scheduler.add_job(hourly_job, "interval", hours=1)

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    yield 
    scheduler.shutdown() 

Base.metadata.create_all(bind=engine)
app = FastAPI(lifespan=lifespan)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

SECRET_KEY = os.environ.get("JWT_SECRET")
ALGORITHM = os.environ.get("ALGORITHM")

TTL = 20 * 60

class UserLogin(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class PreferenceCreate(BaseModel):
    language: str
    min_stars: int

def run_discovery(language: str, min_stars: int):
    key = f"{language}:{min_stars}"
    cached = r.get(key)
    if cached is not None:
        return json.loads(cached)
    found = search_repos(language, min_stars)[:10]
    batch_result = get_issues_batch(found, min_stars)
    non_empty = [x for x in batch_result["results"] if x.get("issues")]
    result = {"results": non_empty, "failed": batch_result["failed"]}
    r.setex(key, TTL, json.dumps(result))
    return result

def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

@app.post("/register")
def register(user: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == user.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")
    
    hashed = hash_password(user.password)
    
    new_user = User(username=user.username, email=user.email, hashed_password=hashed)
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {"id": new_user.id, "username": new_user.username}

@app.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    payload = {"sub": user.username}
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer"}

@app.get("/issues/{owner}/{repo}")
def get_issues(owner: str, repo: str, min_stars: int = 0):
    try:
        return fetch_open_issues(owner, repo, min_stars)
    except GitHubError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@app.post("/issues/batch")
def issues_batch(repos: list[RepoRequest], min_stars: int = 0):
    return get_issues_batch(repos, min_stars)


@app.post("/discover")
def discover(language: str, min_stars: int = 100, current_user: User = Depends(get_current_user)):
    try:
        return run_discovery(language, min_stars)
    except GitHubError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@app.post("/discover/from-preference/{preference_id}")
def discover_from_preference(preference_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    pref = db.query(Preference).filter(Preference.id == preference_id).first()
    if pref is None or pref.user_id != current_user.username:    # ne postoji ILI nije tvoja
        raise HTTPException(status_code=404, detail="Preference not found")
    try:
        return run_discovery(pref.language, pref.min_stars)
    except GitHubError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@app.post("/preferences")
def create_preference(pref: PreferenceCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    new_pref = Preference(
        user_id=current_user.username,
        language=pref.language,
        min_stars=pref.min_stars,
    )

    db.add(new_pref)
    db.commit()
    db.refresh(new_pref)
    
    return new_pref

#test
@app.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"username": user.username}

@app.get("/test-email")
def test_email(current_user: User = Depends(get_current_user)):
    if current_user.email is None:
        raise HTTPException(status_code=400, detail="No email on file for this user")
    send_email(current_user.email, "Test", "Radi li ovo?")
    return {"sent": True}