import os
import tempfile
import shutil
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, Header
from services.image_utils import ensure_landscape_for_student
from services.common_ocr import clova_ocr
from services.verify_student import validate_student_card
from services.verify_license import validate_license_document

router = APIRouter(prefix="/ocr")

OCR_INTERNAL_TOKEN = os.getenv("OCR_INTERNAL_TOKEN", "") 

def verify_internal_token(authorization: Optional[str]) -> None:
    if not OCR_INTERNAL_TOKEN:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization")
    token = authorization.split(" ", 1)[1].strip()
    if token != OCR_INTERNAL_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")

@router.post("/student")
async def ocr_student(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    verify_internal_token(authorization)
    if not file.filename:
        raise HTTPException(status_code=400, detail="파일명이 없습니다.")
    if file.content_type not in {"image/jpeg", "image/jpg", "image/png"}:
        raise HTTPException(status_code=400, detail="지원하지 않는 파일 형식입니다.")

    original_path = save_temp_file(file)
    processed_path = original_path
    try:
        # ✅ 가로형 학생증 자동 방향 보정
        processed_path = ensure_landscape_for_student(original_path, clova_ocr.ocr_lines)

        result = validate_student_card(processed_path)
        result.setdefault("fields", {"name": "", "studentId": "", "university": ""})
        result.setdefault("documentType", "student")
        if not result.get("valid") and "오류" not in result.get("message", ""):
            result["message"] = "인증할 수 없는 학생증입니다."
        return result
    finally:
        # 임시파일 정리 (원본 + 보정본)
        cleanup_temp_file(original_path)
        if processed_path != original_path:
            cleanup_temp_file(processed_path)

@router.post("/professional")
async def ocr_professional(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    verify_internal_token(authorization)
    if not file.filename:
        raise HTTPException(status_code=400, detail="파일명이 없습니다.")
    if file.content_type not in {"image/jpeg", "image/jpg", "image/png"}:
        raise HTTPException(status_code=400, detail="지원하지 않는 파일 형식입니다.")
    path = save_temp_file(file)
    try:
        result = validate_license_document(path)
        result.setdefault("fields", {"name": "", "licenseNumber": "", "issueDate": ""})
        result.setdefault("documentType", "license")
        if not result.get("valid") and "오류" not in result.get("message", ""):
            result["message"] = "인증할 수 없는 면허증입니다."
        return result
    finally:
        cleanup_temp_file(path)

@router.get("/health")
async def health_check():
    url = os.getenv("CLOVA_OCR_URL")
    key = os.getenv("CLOVA_SECRET_KEY")
    if not url or not key or key == "your-secret-key-here":
        return {"status": "warning", "message": "Clova OCR API 설정이 필요합니다.", "ocr_engine": "clova", "config_status": "incomplete"}
    return {"status": "healthy", "message": "OCR 서비스가 정상 작동 중입니다.", "ocr_engine": "clova", "config_status": "complete"}

        
def save_temp_file(upload_file: UploadFile) -> str:
    """업로드된 파일을 임시 파일로 저장"""
    suffix = upload_file.filename.split(".")[-1] if upload_file.filename else "jpg"
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f".{suffix}")
    with temp_file as f:
        shutil.copyfileobj(upload_file.file, f)
    return temp_file.name

def cleanup_temp_file(file_path: str):
    """임시 파일 정리"""
    try:
        if os.path.exists(file_path):
            os.unlink(file_path)
    except Exception as e:
        print(f"[⚠️ 임시파일 삭제 실패] {file_path}: {e}")
