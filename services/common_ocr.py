import os
import re
from typing import Dict, List, Tuple
from dotenv import load_dotenv

from services.clova_ocr import ClovaOCR
from services.visualize import visualize_ocr_result

load_dotenv()

CLOVA_OCR_URL = os.getenv("CLOVA_OCR_URL")
CLOVA_SECRET_KEY = os.getenv("CLOVA_SECRET_KEY")
clova_ocr = ClovaOCR(CLOVA_OCR_URL, CLOVA_SECRET_KEY)

PHARMACY_KEYWORDS = ["약학과", "약학대학", "약대", "약학", "PHARMACY"]
STUDENT_CARD_KWS  = ["학생증", "학번", "대학교", "Student ID", "학과", "STUDENT", "ID CARD"]

LICENSE_REQUIRED_KWS = {"면허증", "보건복지부"}
LICENSE_NICE_KWS     = {"약사법", "제3조", "장관", "의약"}

LICENSE_NO_PATTERNS = [
    r"제?\s*(\d{4,7})\s*호",
    r"\b(\d{4,7})[-]?\d{0,3}\b",
]

NAME_STOPWORDS = {
    "학생증", "학번", "대학교", "대학", "학과", "단과대학", "학부", "총장", "교수",
    "School", "University", "UNIVERSITY", "College", "Department",
}

def visualize_save_path(image_path: str, suffix: str) -> str:
    base, ext = os.path.splitext(image_path)
    return f"{base}_{suffix}{ext}"

def correct_typos(text: str) -> str:
    typo_map = {
        "약차과": "약학과", "약차대점": "약학대학", "양한대": "약학대학",
        "약학과대": "약학과", "약학대": "약학대학", "약학대학학": "약학대학",
    }
    for w, r in typo_map.items():
        text = text.replace(w, r)
    return text

def is_likely_student_card(text: str) -> bool:
    t = text.lower()
    return any(k.lower() in t for k in STUDENT_CARD_KWS)

def has_pharmacy_major(text: str) -> bool:
    t = correct_typos(text)
    return any(k.lower() in t.lower() for k in PHARMACY_KEYWORDS)

def merge_lines_by_y(sorted_boxes, y_thresh=15) -> List[str]:
    merged, current, prev_y = [], [], None
    for box in sorted_boxes:
        text = box[1][0]
        y1 = box[0][0][1]
        y3 = box[0][2][1]
        y_center = int((y1 + y3) / 2)
        if prev_y is None or abs(y_center - prev_y) < y_thresh:
            current.append(text)
        else:
            merged.append(" ".join(current)); current = [text]
        prev_y = y_center
    if current:
        merged.append(" ".join(current))
    return merged

def _kname_candidates_from_line(line: str) -> List[str]:
    return re.findall(r"[가-힣]{2,4}", line)

def _is_bad_name_token(token: str) -> bool:
    # stopwords 사전 매칭
    if token in NAME_STOPWORDS:
        return True
    # 대학/대학교/학부/학과 등으로 끝나는 경우 제외
    if re.search(r"(대학교|대학원|대학|학과|학부)$", token):
        return True
    return False


def extract_name_heuristic(text: str, lines: List[str]) -> str:
    KEYWORDS_NEG = ("학생증", "대학교", "대학", "학과", "총장", "UNIVERSITY", "College", "Department")
    KEYWORDS_POS = ("성명", "이름")
    scored: List[Tuple[str, float]] = []
    text_counts: Dict[str, int] = {}
    for line in lines:
        for cand in _kname_candidates_from_line(line):
            text_counts[cand] = text_counts.get(cand, 0) + 1
    for line in lines:
        base_line_score = 0.0
        if len(line) <= 8: base_line_score += 1.5
        if any(k in line for k in KEYWORDS_POS): base_line_score += 1.0
        if any(k in line for k in KEYWORDS_NEG): base_line_score -= 1.5
        for cand in _kname_candidates_from_line(line):
            if _is_bad_name_token(cand):
                continue
            score = 1.0 + base_line_score
            if text_counts.get(cand, 0) == 1: score += 0.7
            if cand in {"약학대학", "약학과"}: score -= 1.2
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

def extract_department_regex(text: str) -> str:
    t = correct_typos(text)

    # 1) 한글 후보 수집
    #    예) 약학과, 컴퓨터공학과, 경영학부, 약학대학, 약학대학원
    cand_iter = re.finditer(r"[가-힣A-Za-z]{2,30}(학과|전공|학부|대학|대학원)", t)
    cands = [m.group(0) for m in cand_iter]

    def rank(dep: str) -> tuple:
        # 랭크 키: (약학 포함 우선, 세부도 우선, 길이 음수로 긴 것 우선)
        has_pharm = ("약학" in dep)
        # 상세도 점수: 학과/전공(0) < 학부(1) < 대학/대학원(2)
        if dep.endswith(("학과", "전공")):
            detail = 0
        elif dep.endswith("학부"):
            detail = 1
        else:  # 대학/대학원
            detail = 2
        return (0 if has_pharm else 1, detail, -len(dep))

    if cands:
        cands.sort(key=rank)
        best = cands[0]
        return best

    # 2) 영문 표현 처리
    m = re.search(r"(College|School|Faculty)\s+of\s+(Pharmacy|Pharmaceutical\w*)", t, re.IGNORECASE)
    if m:
        # 한국어 통일 명칭으로 반환
        if re.search(r"Graduate|Postgraduate|Graduate School", t, re.IGNORECASE):
            return "약학대학원"
        return "약학대학"

    # 3) 키워드 기반 폴백
    if "약학대학" in t:
        return "약학대학"
    if re.search(r"\bPHARMACY\b", t, re.IGNORECASE):
        return "약학과"
    if has_pharmacy_major(t):
        # 약학 키워드가 확인되면 최소 '약학과'로 폴백
        return "약학과"

    return ""

def collapse_spaced_hangul(seq: str) -> str:

    tokens = seq.strip().split()
    if 2 <= len(tokens) <= 4 and all(re.fullmatch(r"[가-힣]", t) for t in tokens):
        return "".join(tokens)
    return seq

def normalize_kor_date(s: str) -> str:

    s = s.strip()

    # 1) YYYY년 M월 D일
    m = re.search(r"(20\d{2})\s*년\s*(0?[1-9]|1[0-2])\s*월\s*(0?[1-9]|[12]\d|3[01])\s*일", s)
    if m:
        y, mo, d = m.group(1), m.group(2), m.group(3)
        return f"{y}-{int(mo):02d}-{int(d):02d}"

    # 2) M월 D일 YYYY년  ← 샘플 케이스
    m = re.search(r"(0?[1-9]|1[0-2])\s*월\s*(0?[1-9]|[12]\d|3[01])\s*일\s*(20\d{2})\s*년", s)
    if m:
        mo, d, y = m.group(1), m.group(2), m.group(3)
        return f"{y}-{int(mo):02d}-{int(d):02d}"

    # 3) 숫자 구분자 스타일
    m = re.search(r"(20\d{2})[.\-/](0?[1-9]|1[0-2])[.\-/](0?[1-9]|[12]\d|3[01])", s)
    if m:
        y, mo, d = m.group(1), m.group(2), m.group(3)
        return f"{y}-{int(mo):02d}-{int(d):02d}"

    return ""