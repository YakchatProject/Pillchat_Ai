import re
from services.ocr_models import create_ocr_model
from services.image_utils import is_vertical_card, is_card_like
from services.field_extractor import extract_all_fields_from_lines
from services.license_extractor import extract_license_fields
from services.preprocess import preprocess_image
from services.visualize import visualize_ocr_result


PHARMACY_KEYWORDS = ['약학과', '약학대학', '약대', '약학', '藥學科']

KEYWORDS = ['학생증', '학번', '대학교', 'Student ID', '학과']

def correct_typos(text: str) -> str:
    typo_map = {
        '약차과': '약학과',
        '약차대점': '약학대학',
    }
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
        if re.search(r'20[0-9]{6,8}', line):  # 학번 있는 줄 우선
            candidates = re.findall(r'[가-힣]{2,4}', line)
            for c in candidates:
                if '대학교' not in c and '학과' not in c:
                    return c

    if lines:
        fallback = re.findall(r'[가-힣]{2,4}', lines[0])
        return fallback[0] if fallback else ''
    return ''


def extract_student_id_regex(text: str) -> str:
    match = re.search(r'20[0-9]{6,8}', text.replace(' ', ''))
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


def try_student_ocr(image_path: str, preprocess: bool) -> dict:
    if preprocess:
        image_path = preprocess_image(image_path)

    rec_shape = '3, 64, 320' if is_vertical_card(image_path) else '3, 32, 640'

    ocr_model = create_ocr_model(rec_shape)
    result = ocr_model.ocr(image_path, cls=True)

    # ✅ 시각화 저장
    visualize_ocr_result(image_path, result, save_path=image_path.replace(".", "_ocr."))

    # ✅ Y축 기준 정렬로 line 재구성
    sorted_result = sorted(result[0], key=lambda box: box[0][0][1])
    lines = [line[1][0] for line in sorted_result]
    full_text = correct_typos(' '.join(lines).replace(" ", ""))

    is_student_card = is_likely_student_card(full_text)
    has_pharmacy = has_pharmacy_major(full_text)

    # ✅ OCR 누락 대비 fallback
    if not has_pharmacy and '약학' in full_text:
        has_pharmacy = True

    looks_like_card = is_card_like(image_path, result)
    fields = extract_all_fields_from_lines(lines)

    return {
        "valid": is_student_card and has_pharmacy and looks_like_card,
        "is_student_card": is_student_card,
        "has_pharmacy": has_pharmacy,
        "looks_like_card": looks_like_card,
        "text": full_text,
        "fields": fields,
        "text_length": len(full_text)
    }



def validate_student_card_with_fallback(image_path: str) -> dict:
    result_raw = try_student_ocr(image_path, preprocess=False)
    if result_raw['valid']:
        return result_raw

    result_pre = try_student_ocr(image_path, preprocess=True)
    if result_pre['valid']:
        return result_pre

    return result_pre if result_pre['text_length'] > result_raw['text_length'] else result_raw


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
