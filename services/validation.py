from paddleocr import PaddleOCR
from PIL import Image
from services.field_extractor import extract_all_fields_from_lines
from services.license_extractor import extract_license_fields
from services.preprocess import preprocess_image
ocr_model = PaddleOCR(
    use_angle_cls=True,
    lang='korean',
    det_db_box_thresh=0.6,
    det_db_unclip_ratio=1.5,
    drop_score=0.5,
    rec_algorithm='CRNN',            
    rec_image_shape='3, 32, 320',   
    max_text_length=30                
)

KEYWORDS = ['학생증', '학번', '대학교', 'Student ID', '학과']
PHARMACY_KEYWORDS = [
    '약학과', '약대', '약학대학', '약 사 학 과',
    '약차과', '약차대점', '약학', '藥學科'  
]

def has_pharmacy_major(text: str) -> bool:
    return any(k in text for k in PHARMACY_KEYWORDS)

def is_likely_student_card(text: str) -> bool:
    return any(keyword in text for keyword in KEYWORDS)

def is_card_aspect_ratio(image_path: str, min_ratio=1.4) -> bool:
    img = Image.open(image_path)
    width, height = img.size
    return width / height >= min_ratio

def get_text_density(ocr_result) -> float:
    total_box_area = 0
    for box in ocr_result[0]:
        points = box[0]
        x0, y0 = points[0]
        x2, y2 = points[2]
        w, h = abs(x2 - x0), abs(y2 - y0)
        total_box_area += w * h
    return total_box_area

def is_card_like(image_path: str, ocr_result) -> bool:
    aspect_ok = is_card_aspect_ratio(image_path)
    density_ok = get_text_density(ocr_result) > 30000
    return aspect_ok or density_ok

def validate_student_card(image_path: str, preprocess: bool = False) -> dict:
    if preprocess:
        image_path = preprocess_image(image_path)

    result = ocr_model.ocr(image_path, cls=True)
    lines = [line[1][0] for line in result[0]]
    full_text = ' '.join(lines)

    is_student_card = is_likely_student_card(full_text)
    has_pharmacy = has_pharmacy_major(full_text) 
    looks_like_card = is_card_like(image_path, result)

    fields = extract_all_fields_from_lines(lines)

    return {
        "valid": is_student_card and has_pharmacy and looks_like_card,
        "is_student_card": is_student_card,
        "has_pharmacy": has_pharmacy,
        "looks_like_card": looks_like_card,
        "text": full_text,
        "fields": fields
    }



def validate_license_document(image_path: str, preprocess: bool = True) -> dict:
    import time
    start = time.time()

    if preprocess:
        image_path = preprocess_image(image_path)

    result = ocr_model.ocr(image_path, cls=True)

    print(f"[⏱️ OCR TIME] {time.time() - start:.2f}s")
    lines = [line[1][0] for line in result[0]]
    full_text = ' '.join(lines)

    required_keywords = ['면허증', '보건복지부']
    valid = all(k in full_text for k in required_keywords)

    fields = extract_license_fields(lines, full_text)
    if not all([fields['name'], fields['licenseNumber'], fields['issueDate']]):
        valid = False

    print("[🔍 OCR Lines]", lines)
    print("[📝 Full Text]", full_text)

    return {
        "valid": valid,
        "text": full_text,
        "fields": fields
    }
