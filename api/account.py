from fastapi import APIRouter, Depends, HTTPException, Request, Response, Cookie
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from database import SessionLocal, User
import requests
from datetime import datetime
from itsdangerous import URLSafeSerializer
from dotenv import load_dotenv
import os

router = APIRouter()

load_dotenv()  # .env 파일 로드
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
SECRET_KEY = os.getenv("SECRET_KEY")

REDIRECT_URI = "http://127.0.0.1:8000/auth/naver/callback"

# 네이버 로그인 관련 URL
NAVER_AUTH_URL = "https://nid.naver.com/oauth2.0/authorize"
NAVER_TOKEN_URL = "https://nid.naver.com/oauth2.0/token"
NAVER_USER_INFO_URL = "https://openapi.naver.com/v1/nid/me"

# 데이터베이스 세션 종속성
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 로그인 URL 생성
@router.get("/auth/naver/login")
def login():
    # 네이버 로그인 URL로 리다이렉트
    return RedirectResponse(
        f"{NAVER_AUTH_URL}?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&state=12345"
    )

# 네이버 로그인 콜백 처리
@router.get("/auth/naver/callback")
def callback(request: Request, response: Response, db: Session = Depends(get_db)):
    # 네이버로부터 전달된 코드와 상태 파라미터 수집
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    # 네이버에 토큰 요청
    token_response = requests.post(
        NAVER_TOKEN_URL,
        params={
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "state": state,
        },
    )
    token_json = token_response.json()
    access_token = token_json.get("access_token")

    # 액세스 토큰이 없으면 에러 반환
    if not access_token:
        raise HTTPException(status_code=400, detail="Failed to get access token")

    # 쿠키에 액세스 토큰 저장
    serializer = URLSafeSerializer(SECRET_KEY)
    signed_token = serializer.dumps(access_token)
    response.set_cookie(key="access_token", value=signed_token, httponly=True)

    # 네이버로부터 사용자 정보 요청
    user_response = requests.get(
        NAVER_USER_INFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    user_info = user_response.json()

    # 사용자 정보 요청 실패 시 에러 반환
    if user_info.get("resultcode") != "00":
        raise HTTPException(status_code=400, detail="Failed to get user info")

    user_detail = user_info.get("response")

    # 사용자 정보 추출
    email = user_detail.get("email")
    name = user_detail.get("name")
    phone_number = user_detail.get("mobile")
    birth_date = datetime.strptime(user_detail.get("birthday"), "%m-%d").replace(year=int(user_detail.get("birthyear")))
    gender = user_detail.get("gender")

    # 사용자 존재 여부 확인 및 회원가입 처리
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            name=name,
            phone_number=phone_number,
            birth_date=birth_date,
            gender=gender
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return {"email": user.email, "name": user.name, "phone_number": user.phone_number, "birth_date": user.birth_date,
            "gender": user.gender}

# 로그아웃
@router.get("/auth/naver/logout")
def logout(response: Response):
    # 쿠키에서 액세스 토큰 삭제
    response.delete_cookie(key="access_token")
    return {"message": "Successfully logged out"}

# 회원 탈퇴
@router.get("/auth/naver/withdraw", response_model=dict)
def withdraw(db: Session = Depends(get_db), access_token: str = Cookie(None)):
    # 쿠키에서 액세스 토큰이 없으면 에러 반환
    if not access_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # 쿠키에서 서명된 토큰을 읽고 검증
    serializer = URLSafeSerializer(SECRET_KEY)
    try:
        token = serializer.loads(access_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # 네이버로부터 사용자 정보 요청
    user_response = requests.get(
        NAVER_USER_INFO_URL,
        headers={"Authorization": f"Bearer {token}"},
    )
    user_info = user_response.json()

    # 사용자 정보 요청 실패 시 에러 반환
    if user_info.get("resultcode") != "00":
        raise HTTPException(status_code=400, detail="Failed to get user info")

    user_detail = user_info.get("response")
    email = user_detail.get("email")

    # 데이터베이스에서 사용자 삭제
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"message": "Successfully withdrew"}
