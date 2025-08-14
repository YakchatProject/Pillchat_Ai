# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.ocr_route import router as ocr_router

app = FastAPI(title="PillChat OCR 인증 서버")

# CORS 설정 (필요시 도메인 제한 가능)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    """간단한 헬스 체크 엔드포인트"""
    return {"status": "ok"}

# 라우터 등록
app.include_router(ocr_router)

@app.get("/")
def root():
    return {"message": "PillChat OCR 서버 작동 중"}
