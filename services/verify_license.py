import os
import re
from typing import Dict, List
from services.common_ocr import (
    clova_ocr, visualize_ocr_result, visualize_save_path,
    LICENSE_REQUIRED_KWS, LICENSE_NICE_KWS, LICENSE_NO_PATTERNS,
    normalize_kor_date, collapse_spaced_hangul,
)
from services.image_utils import ensure_upright_for_license

BLOCKLIST = {"보건복지부", "면허증", "약사법", "장관", "MINISTRY", "HEALTH", "WELFARE"}
BLOCKLIST_SUBSTRINGS = {"보건복지", "보건", "복지"} 
NAME_TRAILING_NOISE = {"명", "성"}

def _is_blocked(token: str) -> bool:
    if token in BLOCKLIST:
        return True
    return any(sub in token for sub in BLOCKLIST_SUBSTRINGS)

def clean_person_name(n: str) -> str:
    """
    후보 이름에서 '명', '성' 같은 꼬리 토큰 제거, 불필요 문자 제거.
    결과가 2~4자 한글이 아니면 빈 문자열 반환.
    """
    n = re.sub(r"[^가-힣]", "", n or "")  # 한글만
    if len(n) >= 3 and n[-1] in NAME_TRAILING_NOISE:
        n = n[:-1]
    # 길이/문자 검증
    if not (2 <= len(n) <= 4) or not re.fullmatch(r"[가-힣]{2,4}", n):
        return ""
    return n

def _pick_name_candidates(text: str) -> List[str]:
    cands: List[tuple[str, float]] = []

    # 1) '약사' 다음
    for m in re.finditer(r"약사\s+([가-힣](?:\s*[가-힣]){1,3})", text):
        raw = collapse_spaced_hangul(m.group(1))
        c = clean_person_name(raw)
        if c and not _is_blocked(c):
            cands.append((c, 2.0))

    # 2) '성명' 다음
    for m in re.finditer(r"성명[:\s]*([가-힣](?:\s*[가-힣]){1,3})", text):
        raw = collapse_spaced_hangul(m.group(1))
        c = clean_person_name(raw)
        if c and not _is_blocked(c):
            cands.append((c, 1.5))

    # 3) 띄어진 단음절 → 결합
    for m in re.finditer(r"([가-힣](?:\s+[가-힣]){1,3})", text):
        raw = collapse_spaced_hangul(m.group(1))
        c = clean_person_name(raw)
        if c and not _is_blocked(c):
            cands.append((c, 1.0))

    # 4) 일반 2~4자 연속 한글
    for m in re.finditer(r"[가-힣]{2,4}", text):
        raw = m.group(0)
        c = clean_person_name(raw)
        if c and not _is_blocked(c):
            cands.append((c, 0.8))

    # dedupe + 위치 보정
    seen = set()
    scored: List[tuple[str, float]] = []
    for c, base in cands:
        if c in seen:
            continue
        seen.add(c)
        score = base + (0.3 if 0 <= text.find(c) <= 80 else 0.0)
        if len(c) >= 3:
            score += 0.2
        scored.append((c, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [c for c, _ in scored]


def _extract_license_fields(text: str) -> Dict[str, str]:
    out = {"name": "", "licenseNumber": "", "issueDate": ""}

    # 이름
    for c in _pick_name_candidates(text):
        out["name"] = c
        break

    # 면허번호
    for pat in LICENSE_NO_PATTERNS:
        m = re.search(pat, text)
        if m:
            out["licenseNumber"] = m.group(1)
            break

    # 발급일
    dm = re.search(r"(발급일|발행일|교부일|일자)[:\s]*([0-9.\-\s년월일]+)", text)
    if dm:
        iso = normalize_kor_date(dm.group(2))
        if iso:
            out["issueDate"] = iso
    if not out["issueDate"]:
        pats = [
            r"(20\d{2})\s*년\s*(0?[1-9]|1[0-2])\s*월\s*(0?[1-9]|[12]\d|3[01])\s*일",
            r"(0?[1-9]|1[0-2])\s*월\s*(0?[1-9]|[12]\d|3[01])\s*일\s*(20\d{2})\s*년",
            r"(20\d{2})[.\-/](0?[1-9]|1[0-2])[.\-/](0?[1-9]|[12]\d|3[01])",
        ]
        for p in pats:
            for m in re.finditer(p, text):
                iso = normalize_kor_date(m.group(0))
                if iso:
                    out["issueDate"] = iso
                    break
            if out["issueDate"]:
                break

    # 🔒 최종 안전망: 여전히 블록이면 이름 비우기 → 다음 로직에서 invalid 처리되도록
    if out["name"]:
        out["name"] = clean_person_name(out["name"])
    if out["name"] and _is_blocked(out["name"]):
        out["name"] = ""

    return out

def validate_license_document(image_path: str) -> Dict:
    """
    routes/ocr_route.py 가 import 하는 공개 함수.
    """
    # 1) 먼저 방향 보정 (0/±90 중 최적 선택)
    upright_path = ensure_upright_for_license(image_path, clova_ocr.ocr_lines)

    # 2) 보정된 경로로 OCR 실행
    result = clova_ocr.ocr(upright_path)
    try:
        visualize_ocr_result(
            upright_path,
            result,
            save_path=visualize_save_path(upright_path, "clova_license_ocr"),
        )
    except Exception:
        pass

    # 3) 텍스트 결합
    lines: List[str] = [b[1][0] for b in result[0] if float(b[1][1]) >= 0.70]
    full_text = " ".join(lines)

    # 4) 키워드/필드 추출
    has_required_keywords = all(k in full_text for k in LICENSE_REQUIRED_KWS)
    keyword_score = sum(k in full_text for k in LICENSE_NICE_KWS)

    fields = _extract_license_fields(full_text)
    has_required_fields = all([
        fields.get("name"),
        fields.get("licenseNumber"),
        fields.get("issueDate"),
    ])

    valid = bool(has_required_keywords and has_required_fields)
    out = {
        "valid": valid,
        "documentType": "license",
        "text": full_text,
        "fields": fields,
        "has_required_keywords": has_required_keywords,
        "has_required_fields": has_required_fields,
        "keyword_score": keyword_score,
        "ocr_engine": "clova",
    }

    # 5) 임시 보정 이미지 정리
    try:
        if upright_path != image_path and os.path.exists(upright_path):
            os.unlink(upright_path)
    except Exception:
        pass

    return out