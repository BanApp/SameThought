from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import SessionLocal, User
from typing import List, Dict
import uuid

# APIRouter를 사용하여 라우터 인스턴스 생성
router = APIRouter()

# 메모리 내에서 채팅 방을 관리하기 위한 데이터 구조
# 채팅 방 ID를 키로 하고, 각 방에 연결된 WebSocket 리스트를 값으로 하는 딕셔너리
active_connections: Dict[str, List[WebSocket]] = {}

# 사용자 간의 요청을 추적하기 위한 데이터 구조
# 요청자의 이메일을 키로 하고, 요청된 사용자의 이메일을 값으로 하는 딕셔너리
user_requests: Dict[str, str] = {}

# 데이터베이스 세션 종속성
# 요청이 끝날 때마다 데이터베이스 세션을 닫기 위해 사용
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 요청 본문 형식을 정의하기 위한 Pydantic 모델
class ChatRequest(BaseModel):
    requester_email: str
    requested_email: str

# 채팅 요청 API
@router.post("/chat/request")
def chat_request(request: ChatRequest, db: Session = Depends(get_db)):
    # 요청자와 요청된 사용자를 데이터베이스에서 조회
    requester = db.query(User).filter(User.email == request.requester_email).first()
    requested = db.query(User).filter(User.email == request.requested_email).first()

    # 사용자 존재 여부 확인
    if not requester or not requested:
        raise HTTPException(status_code=404, detail="User not found")

    # 요청자와 요청된 사용자를 추적하는 딕셔너리에 추가
    user_requests[request.requester_email] = request.requested_email
    return {"message": "Chat request sent"}

# 채팅 수락 API
@router.post("/chat/accept")
def chat_accept(request: ChatRequest, db: Session = Depends(get_db)):
    # 요청된 채팅 요청이 존재하는지 확인
    if user_requests.get(request.requester_email) != request.requested_email:
        raise HTTPException(status_code=400, detail="Chat request not found")

    # 채팅 방 ID 생성
    room_id = str(uuid.uuid4())
    # 새로 생성된 채팅 방 ID를 키로 하고, 빈 리스트를 값으로 하는 딕셔너리에 추가
    active_connections[room_id] = []
    return {"room_id": room_id}

# WebSocket 채팅 엔드포인트
@router.websocket("/ws/chat/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    # WebSocket 연결 수락
    await websocket.accept()
    # 채팅 방 ID가 유효한지 확인
    if room_id not in active_connections:
        # 유효하지 않으면 연결 종료
        await websocket.close(code=1000)
        return

    # 채팅 방에 WebSocket 연결 추가
    active_connections[room_id].append(websocket)

    try:
        # 무한 루프를 통해 메시지 수신 대기
        while True:
            data = await websocket.receive_text()
            # 수신한 메시지를 같은 채팅 방에 있는 다른 모든 연결에 전송
            for connection in active_connections[room_id]:
                if connection != websocket:
                    await connection.send_text(data)
    except WebSocketDisconnect:
        # WebSocket 연결이 끊어진 경우 연결 제거
        active_connections[room_id].remove(websocket)
        # 채팅 방에 더 이상 연결이 없으면 방 삭제
        if not active_connections[room_id]:
            del active_connections[room_id]
