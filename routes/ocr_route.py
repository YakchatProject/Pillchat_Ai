import os
import tempfile
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException, Header
from fastapi.responses import JSONResponse
from services.validation import (
    validate_student_card_with_fallback,
    validate_license_document,
)

router = APIRouter(prefix="/ocr")

# 내부 통신 토큰 (Spring Boot → FastAPI)
OCR_TOKEN = os.getenv("OCR_SERVICE_TOKEN")


def _auth_or_raise(authorization: str | None):
    """Authorization: Bearer <token> 검사. 토큰이 설정된 경우에만 강제."""
    if not OCR_TOKEN:
        # 토큰 미설정이면 인증을 스킵(개발/로컬)
        return
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token == OCR_TOKEN:
            return
    raise HTTPException(status_code=401, detail="Unauthorized")


@router.post("/student")
async def ocr_student(
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
):
    _auth_or_raise(authorization)
    try:
        # 업로드 파일 임시 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as tmp:
            shutil.copyfileobj(file.file, tmp)
            temp_path = tmp.name
        result = validate_student_card_with_fallback(temp_path)
        return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/professional")
async def ocr_professional(
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
):
    _auth_or_raise(authorization)
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as tmp:
            shutil.copyfileobj(file.file, tmp)
            temp_path = tmp.name
        result = validate_license_document(temp_path)
        return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))