import re
import cv2
import os
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

def merge_lines_by_y(sorted_boxes, y_thresh=10):
    merged = []
    current = []
    prev_y = None
    for box in sorted_boxes:
        text = box[1][0]
        y1 = box[0][0][1]
        y2 = box[0][2][1]
        y_center = int((y1 + y2) / 2)

        if prev_y is None or abs(y_center - prev_y) < y_thresh:
            current.append(text)
        else:
            merged.append(' '.join(current))
            current = [text]
        prev_y = y_center

    if current:
        merged.append(' '.join(current))
    return merged


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
        eq = cv2.equalizeHist(gray)
        img = cv2.cvtColor(eq, cv2.COLOR_GRAY2BGR)

    elif level == 'aggressive':
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        blurred = cv2.GaussianBlur(enhanced, (5, 5), 0)
        _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        img = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
        
    elif level == 'denoise_line':
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)

        # Sobel X로 세로 경계 강조
        sobelx = cv2.Sobel(blurred, cv2.CV_64F, 1, 0, ksize=3)
        abs_sobelx = np.absolute(sobelx)
        scaled_sobel = np.uint8(255 * abs_sobelx / np.max(abs_sobelx))

        # 세로선만 추출하기 위한 threshold
        _, thresh = cv2.threshold(scaled_sobel, 120, 255, cv2.THRESH_BINARY)

        # 수직선 모양만 남기기 위한 morphology
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 15))  # 수직선 추출에 특화
        vertical_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

        # 마스크로 선 영역만 흰색으로 덮기
        mask = vertical_lines == 255
        img[mask] = [255, 255, 255]

    else:
        raise ValueError(f"지원하지 않는 전처리 레벨입니다: {level}")

    base, ext = os.path.splitext(image_path)
    save_path = f"{base}_{level}{ext}"
    cv2.imwrite(save_path, img)
    return save_path

def run_ocr_pipeline(image_path: str, level: str) -> dict:
    processed_path = apply_preprocess(image_path, level) if level != 'none' else image_path
    rec_shape = '3, 64, 600' if is_vertical_card(processed_path) else '3, 64, 600'
    ocr_model = create_ocr_model(rec_shape)
    result = ocr_model.ocr(processed_path, cls=True)
    visualize_ocr_result(processed_path, result, save_path=processed_path.replace('.', f'_ocr_{level}.'))

    # score ≥ 0.7 + y축 병합
    sorted_result = sorted(result[0], key=lambda box: box[0][0][1])
    filtered_result = [box for box in sorted_result if box[1][1] >= 0.6]
    lines = merge_lines_by_y(filtered_result)

    full_text = correct_typos(' '.join(lines))

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
    """
    다양한 전처리 레벨을 시도하고, 가장 인식이 잘 된 결과(valid + text_length 기준)를 반환.
    """
    candidates = ['mild', 'medium', 'aggressive', 'denoise_line']
    results = []

    for level in candidates:
        try:
            processed_path = apply_preprocess(image_path, level)
            result = run_ocr_pipeline(processed_path, level)
            result['preprocess_level'] = level  # 나중에 디버깅용으로 레벨 정보도 포함
            results.append(result)
        except Exception as e:
            continue  # 이 레벨 실패하면 무시

    if not results:
        return {
            "valid": False,
            "message": "전처리 및 OCR 실패: 인식 가능한 결과가 없습니다."
        }

    # 1순위: valid=True / 2순위: 텍스트 길이
    best = max(results, key=lambda r: (r['valid'], r['text_length']))

    if not best['valid']:
        best['message'] = "인증할 수 없는 학생증입니다."
    return best


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
