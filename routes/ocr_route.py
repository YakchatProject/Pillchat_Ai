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
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/professional")
async def ocr_professional(file: UploadFile = File(...)):
    image_path = save_temp_file(file)
    try:
        result = validate_license_document(image_path)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
