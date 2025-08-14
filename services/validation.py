import os
import re

from typing import Dict, List, Tuple
from dotenv import load_dotenv

from services.clova_ocr import ClovaOCR
from services.image_utils import is_vertical_card, is_card_like
from services.visualize import visualize_ocr_result 

load_dotenv()

# === 환경변수 ===
CLOVA_OCR_URL = os.getenv("CLOVA_OCR_URL")
CLOVA_SECRET_KEY = os.getenv("CLOVA_SECRET_KEY")
# === 인스턴스 ===
clova_ocr = ClovaOCR(CLOVA_OCR_URL, CLOVA_SECRET_KEY)

# === 키워드/유틸 ===
PHARMACY_KEYWORDS = ["약학과", "약학대학", "약대", "약학", "PHARMACY"]
STUDENT_CARD_KWS  = ["학생증", "학번", "대학교", "Student ID", "학과", "STUDENT", "ID CARD"]

def visualize_save_path(image_path: str, suffix: str) -> str:
    base, ext = os.path.splitext(image_path)
    return f"{base}_{suffix}{ext}"

def correct_typos(text: str) -> str:
    # 약학 관련 OCR 오타 교정 강화
    typo_map = {
        "약차과": "약학과",
        "약차대점": "약학대학",
        "양한대": "약학대학",
        "약학과대": "약학과",
        "약학대": "약학대학",
        "약학대학학": "약학대학",  
    }
    for w, r in typo_map.items():
        text = text.replace(w, r)
    return text

def has_pharmacy_major(text: str) -> bool:
    t = correct_typos(text)
    return any(k.lower() in t.lower() for k in PHARMACY_KEYWORDS)

def is_likely_student_card(text: str) -> bool:
    t = text.lower()
    return any(k.lower() in t for k in STUDENT_CARD_KWS)

def merge_lines_by_y(sorted_boxes, y_thresh=15) -> List[str]:
    """Paddle 유사 포맷 결과 -> Y 기준 라인 병합"""
    merged, current, prev_y = [], [], None
    for box in sorted_boxes:
        text = box[1][0]
        y1 = box[0][0][1]
        y3 = box[0][2][1]
        y_center = int((y1 + y3) / 2)
        if prev_y is None or abs(y_center - prev_y) < y_thresh:
            current.append(text)
        else:
            merged.append(" ".join(current))
            current = [text]
        prev_y = y_center
    if current:
        merged.append(" ".join(current))
    return merged

NAME_STOPWORDS = {
    "학생증", "학번", "대학교", "대학", "학과", "단과대학", "학부", "총장", "교수",
    "School", "University", "UNIVERSITY", "College", "Department",
}

def _kname_candidates_from_line(line: str) -> List[str]:
    # 2~4자 연속 한글(가~힣) 추출
    return re.findall(r"[가-힣]{2,4}", line)

def _is_bad_name_token(token: str) -> bool:
    if token in NAME_STOPWORDS:
        return True

    return False

def extract_name_heuristic(text: str, lines: List[str]) -> str:

    KEYWORDS_NEG = ("학생증", "대학교", "대학", "학과", "총장", "UNIVERSITY", "College", "Department")
    KEYWORDS_POS = ("성명", "이름")

    scored: List[Tuple[str, float]] = []
    text_counts: Dict[str, int] = {}

    # 전체 등장 빈도 계산
    for line in lines:
        for cand in _kname_candidates_from_line(line):
            text_counts[cand] = text_counts.get(cand, 0) + 1

    # 라인 스코어링 + 후보 스코어 계산
    for line in lines:
        line_len = len(line)
        has_neg_kw = any(k in line for k in KEYWORDS_NEG)
        has_pos_kw = any(k in line for k in KEYWORDS_POS)

        base_line_score = 0.0
        if line_len <= 8:
            base_line_score += 1.5
        if has_pos_kw:
            base_line_score += 1.0
        if has_neg_kw:
            base_line_score -= 1.5

        for cand in _kname_candidates_from_line(line):
            if _is_bad_name_token(cand):
                continue
            score = 1.0 + base_line_score
            if text_counts.get(cand, 0) == 1:
                score += 0.7
            # 일반 명사/기관명에 가까운 후보 억제
            if cand in { "약학대학", "약학과"}:
                score -= 1.2

            scored.append((cand, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[0][0] if scored else ""

def extract_student_id_regex(text: str) -> str:
    cleaned = (
        text.upper().replace(" ", "")
        .replace("O", "0").replace("I", "1").replace("L", "1")
        .replace("B", "8").replace("S", "5").replace("Z", "2")
        .replace("에", "")
    )
    m = re.search(r"20[0-9]{6,8}", cleaned)
    return m.group(0) if m else ""

def extract_university_regex(text: str) -> str:
    m = re.search(r"[가-힣]{2,10}대학교|[A-Z]{2,}\s+UNIVERSITY", text, re.IGNORECASE)
    return m.group(0) if m else ""

def extract_fields_simple(lines: List[str]) -> Dict:
    full_text = " ".join(lines)
    return {
        "name": extract_name_heuristic(full_text, lines),  
        "studentId": extract_student_id_regex(full_text),
        "university": extract_university_regex(full_text),
    }

def extract_license_fields_simple(text: str) -> Dict[str, str]:
    out = {"name": "", "licenseNumber": "", "issueDate": ""}
    n = re.search(r"[가-힣]{2,4}", text)
    if n: out["name"] = n.group(0)
    no = re.search(r"\d{5,}-?\d{1,}", text)
    if no: out["licenseNumber"] = no.group(0)
    d = re.search(r"(20\d{2}[.\-](0?[1-9]|1[0-2])[.\-](0?[1-9]|[12]\d|3[01]))", text)
    if d: out["issueDate"] = d.group(0)
    return out

# === 메인 로직 ===
def validate_student_card_simple(image_path: str) -> Dict:
    try:
        result = clova_ocr.ocr(image_path)  # [[...]]
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
            "is_student_card": is_student,
            "has_pharmacy": has_pharm,
            "looks_like_card": looks_like,
            "text": full_text,
            "fields": fields,
            "text_length": len(full_text),
            "ocr_engine": "clova",
        }
    except Exception as e:
        return {"valid": False, "message": f"Clova OCR 처리 중 오류: {e}", "ocr_engine": "clova"}

def validate_student_card_with_fallback(image_path: str) -> Dict:
    clova = validate_student_card_simple(image_path)
    if clova.get("text_length", 0) > 10:
        return clova
    # 폴백 (프로젝트에 존재하는 경우만)
    try:
        from services.ocr_models import create_ocr_model
        import cv2  # noqa
        candidates = ["mild", "medium", "aggressive"]
        results = []
        for level in candidates:
            try:
                p = apply_preprocess_legacy(image_path, level)
                r = run_ocr_pipeline_legacy(p, level)
                r["preprocess_level"] = level
                r["ocr_engine"] = "paddle_fallback"
                results.append(r)
            except Exception:
                continue
        if not results:
            return {"valid": False, "message": "OCR 처리 실패: Clova와 PaddleOCR 모두 실패", "ocr_engine": "both_failed"}
        best = max(results, key=lambda r: (r["valid"], r["text_length"]))
        if not best["valid"]:
            best["message"] = "인증할 수 없는 학생증입니다."
        return best
    except ImportError:
        return clova

def validate_license_document(image_path: str) -> Dict:
    try:
        result = clova_ocr.ocr(image_path)
        try:
            visualize_ocr_result(image_path, result, save_path=visualize_save_path(image_path, "clova_license_ocr"))
        except Exception:
            pass

        lines: List[str] = []
        for box in result[0]:
            if float(box[1][1]) >= 0.7:
                lines.append(box[1][0])
        full_text = " ".join(lines)

        required_keywords = ["면허증", "보건복지부"]
        has_required_keywords = all(k in full_text for k in required_keywords)

        fields = extract_license_fields_simple(full_text)
        has_required_fields = all([fields.get("name"), fields.get("licenseNumber"), fields.get("issueDate")])

        valid = bool(has_required_keywords and has_required_fields)
        return {
            "valid": valid,
            "text": full_text,
            "fields": fields,
            "has_required_keywords": has_required_keywords,
            "has_required_fields": has_required_fields,
            "ocr_engine": "clova",
        }
    except Exception as e:
        return {"valid": False, "message": f"Clova OCR 면허증 처리 중 오류: {e}", "ocr_engine": "clova"}

# === (선택) 폴백 구현이 프로젝트에 있을 때만 사용 ===
def apply_preprocess_legacy(image_path: str, level: str) -> str:
    import cv2
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"이미지 파일을 열 수 없음: {image_path}")
    if level == "mild":
        img = cv2.detailEnhance(img, sigma_s=5, sigma_r=0.15)
    elif level == "medium":
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        eq = cv2.equalizeHist(gray)
        img = cv2.cvtColor(eq, cv2.COLOR_GRAY2BGR)
    elif level == "aggressive":
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        import numpy as np  # noqa
        import cv2 as cv
        blurred = cv.GaussianBlur(enhanced, (5, 5), 0)
        _, binary = cv.threshold(blurred, 0, 255, cv.THRESH_BINARY + cv.THRESH_OTSU)
        img = cv.cvtColor(binary, cv.COLOR_GRAY2BGR)
    base, ext = os.path.splitext(image_path)
    save_path = f"{base}_{level}{ext}"
    cv2.imwrite(save_path, img)
    return save_path

def run_ocr_pipeline_legacy(image_path: str, level: str) -> Dict:
    from services.ocr_models import create_ocr_model
    rec_shape = "3, 64, 600" if is_vertical_card(image_path) else "3, 64, 600"
    ocr_model = create_ocr_model(rec_shape)
    result = ocr_model.ocr(image_path, cls=True)

    sorted_result = sorted(result[0], key=lambda b: b[0][0][1])
    filtered = [b for b in sorted_result if float(b[1][1]) >= 0.6]
    lines = merge_lines_by_y(filtered, y_thresh=10)

    full_text = correct_typos(" ".join(lines))

    is_student = is_likely_student_card(full_text)
    has_pharm = has_pharmacy_major(full_text) or ("약학" in full_text)
    looks_like = is_card_like(image_path, result)
    fields = extract_fields_simple(lines)
    valid = bool(is_student and has_pharm and looks_like)

    return {
        "valid": valid,
        "is_student_card": is_student,
        "has_pharmacy": has_pharm,
        "looks_like_card": looks_like,
        "text": full_text,
        "fields": fields,
        "text_length": len(full_text),
    }
