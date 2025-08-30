from typing import Dict, List
from services.image_utils import is_card_like
from services.common_ocr import (
    clova_ocr, visualize_ocr_result, visualize_save_path,
    correct_typos, is_likely_student_card, has_pharmacy_major,
    merge_lines_by_y, extract_name_heuristic,
    extract_student_id_regex, extract_university_regex,extract_department_regex,
)

def extract_fields_simple(lines: List[str]) -> Dict:
    full_text = " ".join(lines)
    return {
        "name": extract_name_heuristic(full_text, lines),
        "studentId": extract_student_id_regex(full_text),
        "university": extract_university_regex(full_text),
        "department": extract_department_regex(full_text),
    }

def validate_student_card(image_path: str) -> Dict:
    result = clova_ocr.ocr(image_path)
    try:
        visualize_ocr_result(image_path, result, save_path=visualize_save_path(image_path, "clova_ocr"))
    except Exception:
        pass

    sorted_result = sorted(result[0], key=lambda b: b[0][0][1])
    filtered = [b for b in sorted_result if float(b[1][1]) >= 0.8]
    lines = merge_lines_by_y(filtered)
    full_text = correct_typos(" ".join(lines))

    is_student = is_likely_student_card(full_text)
    has_pharm = has_pharmacy_major(full_text) or ("약학" in full_text)
    looks_like = is_card_like(image_path, result)
    fields = extract_fields_simple(lines)

    valid = bool(is_student and has_pharm and looks_like)
    return {
        "valid": valid,
        "documentType": "student",
        "is_student_card": is_student,
        "has_pharmacy": has_pharm,
        "looks_like_card": looks_like,
        "text": full_text,
        "fields": fields,
        "text_length": len(full_text),
        "ocr_engine": "clova",
    }
