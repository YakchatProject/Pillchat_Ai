import re
import cv2
import numpy as np
from services.ocr_models import create_ocr_model
from services.image_utils import is_vertical_card, is_card_like
from services.field_extractor import extract_all_fields_from_lines
from services.license_extractor import extract_license_fields
from services.preprocess import preprocess_image
from services.visualize import visualize_ocr_result


PHARMACY_KEYWORDS = ['약학과', '약학대학', '약대', '약학', '藥學科']
KEYWORDS = ['학생증', '학번', '대학교', 'Student ID', '학과']


def correct_typos(text: str) -> str:
    typo_map = {'약차과': '약학과', '약차대점': '약학대학','양한대': '약학대학', '약학과대': '약학과', '약학대': '약학대학'}
    for wrong, right in typo_map.items():
        text = text.replace(wrong, right)
    return text


def has_pharmacy_major(text: str) -> bool:
    text = correct_typos(text)
    return any(k in text for k in PHARMACY_KEYWORDS)
    
def is_likely_student_card(text: str) -> bool:
    return any(keyword in text for keyword in KEYWORDS)

def extract_name_heuristic(text: str, lines: list[str]) -> str:
    for line in lines:
        name_candidates = re.findall(r'\b[가-힣]{2,4}\b', line)
        for cand in name_candidates:
            if not any(keyword in cand for keyword in ['대학', '과', '학과', '대학교']):
                return cand
    return ''


def extract_student_id_regex(text: str) -> str:
    cleaned = (text.upper()
        .replace(' ', '')
        .replace('O', '0')
        .replace('I', '1')
        .replace('L', '1')
        .replace('B', '8')
        .replace('S', '5')
        .replace('Z', '2')
        .replace('에', '')
    )
    match = re.search(r'20[0-9]{6,8}', cleaned)
    return match.group() if match else ''


def extract_university_regex(text: str) -> str:
    matches = re.findall(r'[가-힣]{2,10}대학교|[A-Z]{2,} UNIVERSITY', text, re.IGNORECASE)
    return matches[0] if matches else ''


def extract_all_fields_from_lines(lines: list[str]) -> dict:
    full_text = ' '.join(lines)
    return {
        "name": extract_name_heuristic(full_text, lines),
        "studentId": extract_student_id_regex(full_text),
        "university": extract_university_regex(full_text),
    }
    
def decide_preprocess_level(image_path: str) -> str:
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    brightness = np.mean(gray)
    contrast = np.std(gray)
    if brightness < 90:
        return 'aggressive'
    elif contrast < 25:
        return 'medium'
    else:
        return 'mild'

def apply_preprocess(image_path: str, level: str) -> str:
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"이미지 파일을 열 수 없음: {image_path}")
    if level == 'mild':
        img = cv2.detailEnhance(img, sigma_s=5, sigma_r=0.15)
    elif level == 'medium':
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        img = cv2.equalizeHist(gray)
    elif level == 'aggressive':
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (3, 3), 0)
        _, img = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    save_path = image_path.replace('.', f'_{level}.')
    cv2.imwrite(save_path, img)
    return save_path

def run_ocr_pipeline(image_path: str, level: str) -> dict:
    processed_path = apply_preprocess(image_path, level) if level != 'none' else image_path
    rec_shape = '3, 64, 320' if is_vertical_card(processed_path) else '3, 32, 640'
    ocr_model = create_ocr_model(rec_shape)
    result = ocr_model.ocr(processed_path, cls=True)
    visualize_ocr_result(processed_path, result, save_path=processed_path.replace('.', f'_ocr_{level}.'))
    sorted_result = sorted(result[0], key=lambda box: box[0][0][1])
    lines = [line[1][0] for line in sorted_result]
    full_text = correct_typos(''.join(lines).replace(" ", ""))

    is_student_card = is_likely_student_card(full_text)
    has_pharmacy = has_pharmacy_major(full_text)
    if not has_pharmacy and '약학' in full_text:
        has_pharmacy = True
    looks_like_card = is_card_like(processed_path, result)
    fields = extract_all_fields_from_lines(lines)
    valid = is_student_card and has_pharmacy and looks_like_card

    return {
        "valid": valid,
        "is_student_card": is_student_card,
        "has_pharmacy": has_pharmacy,
        "looks_like_card": looks_like_card,
        "text": full_text,
        "fields": fields,
        "text_length": len(full_text)
    }

def validate_student_card_with_fallback(image_path: str) -> dict:
    try:
        level = decide_preprocess_level(image_path)
        result = run_ocr_pipeline(image_path, level)
        if not result['valid']:
            result['message'] = "인증할 수 없는 학생증입니다."
        return result
    except Exception as e:
        return {"valid": False, "message": "학생증 처리 중 오류가 발생했습니다.", "error": str(e)}


def validate_license_document(image_path: str, preprocess: bool = True) -> dict:
    if preprocess:
        image_path = preprocess_image(image_path)

    ocr_model = create_ocr_model('3, 32, 320')  # 면허증은 문서 형태
    result = ocr_model.ocr(image_path, cls=True)
    
    visualize_ocr_result(image_path, result, save_path=image_path.replace(".", "_ocr."))

    lines = [line[1][0] for line in result[0]]
    full_text = ' '.join(lines)

    required_keywords = ['면허증', '보건복지부']
    valid = all(k in full_text for k in required_keywords)

    fields = extract_license_fields(lines, full_text)
    if not all([fields['name'], fields['licenseNumber'], fields['issueDate']]):
        valid = False

    return {
        "valid": valid,
        "text": full_text,
        "fields": fields
    }
