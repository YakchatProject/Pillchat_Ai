from fastapi import APIRouter, UploadFile, File, HTTPException
from services.validation import validate_license_document, validate_student_card_with_fallback
import tempfile
import shutil



router = APIRouter(prefix="/ocr")

def save_temp_file(upload_file: UploadFile) -> str:
    suffix = upload_file.filename.split(".")[-1]
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f".{suffix}")
    with temp_file as f:
        shutil.copyfileobj(upload_file.file, f)
    return temp_file.name



@router.post("/student")
async def ocr_student(file: UploadFile = File(...)):
    image_path = save_temp_file(file)
    try:
        result = validate_student_card_with_fallback(image_path)

        if not result.get("valid"):
            result["message"] = "인증할 수 없는 학생증입니다."  # ✔ 정상 유효성 실패 메시지
        return result

    except Exception as e:
        import traceback
        print("[❗예외 발생]", traceback.format_exc())
        return {
            "valid": False,
            "message": "학생증 처리 중 오류가 발생했습니다."  # ✔ 진짜 에러일 경우
        }



@router.post("/professional")
async def ocr_professional(file: UploadFile = File(...)):
    image_path = save_temp_file(file)
    try:
        result = validate_license_document(image_path)
        if not result.get("valid"):
            result["message"] = "인증할 수 없는 면허증입니다."
        return result
    except Exception as e:
        return {"valid": False, "message": "면허증 처리 중 오류가 발생했습니다."}
