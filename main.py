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
from models import Preference, User
from pydantic import BaseModel
import bcrypt
import jwt
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

Base.metadata.create_all(bind=engine)
app = FastAPI()

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
    
    new_user = User(username=user.username, hashed_password=hashed)
    
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
def discover_from_preference(preference_id: int, db: Session = Depends(get_db),
                             current_user: User = Depends(get_current_user)):
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