# services/image_utils.py
from PIL import Image, ImageOps
from typing import Tuple, List
import os
import tempfile

# ------------------------
# 공통: 이미지/회전 유틸
# ------------------------
def _open_exif_transposed(path: str) -> Image.Image:
    """EXIF Orientation을 반영해 똑바로 연 이미지 반환."""
    img = Image.open(path)
    return ImageOps.exif_transpose(img)

def _save_tmp(img: Image.Image, suffix: str = ".jpg") -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    img.save(tmp.name, quality=95)
    return tmp.name

def autorotate_exif(path: str) -> str:
    """EXIF 기준 회전 보정 후 새 파일 경로 반환."""
    img = _open_exif_transposed(path)
    return _save_tmp(img, os.path.splitext(path)[1] or ".jpg")

def rotate90(path: str, cw: bool) -> str:
    """90도 회전(cw=True 시 시계방향) 후 새 파일 경로 반환."""
    img = _open_exif_transposed(path)
    img = img.rotate(-90 if cw else 90, expand=True)
    return _save_tmp(img, os.path.splitext(path)[1] or ".jpg")

# ------------------------
# 면허증 전용: 자동 방향 보정
# ------------------------
_LICENSE_KWS = ("면허증", "보건복지부", "약사법", "제3조", "장관")

def ensure_upright_for_license(path: str, ocr_lines_fn) -> str:
    """
    면허증 입력을 0/±90도 중 가장 '읽기 좋은' 방향으로 보정.
    ocr_lines_fn = ClovaOCR.ocr_lines (image_path, conf_min=...)
    """
    fixed = autorotate_exif(path)
    cands = [fixed, rotate90(fixed, cw=True), rotate90(fixed, cw=False)]
    scored = []
    for p in cands:
        try:
            lines = ocr_lines_fn(p, conf_min=0.6)
            text = " ".join(lines)
            kw = sum(1 for k in _LICENSE_KWS if k in text)
            hangul = sum(1 for ch in text if "가" <= ch <= "힣")
            scored.append((kw, hangul, p))
        except Exception:
            scored.append((0, 0, p))
    scored.sort(reverse=True)  # (kw, hangul) 내림차순
    best = scored[0][2]
    # 나머지 임시 파일 정리
    for _, _, p in scored[1:]:
        try:
            if os.path.exists(p): os.unlink(p)
        except Exception:
            pass
    return best

# ------------------------
# 학생증 전용: 카드 형태 판단
# ------------------------
def is_vertical_card(image_path: str) -> bool:
    """세로가 더 길면 True (EXIF 보정 포함)."""
    with _open_exif_transposed(image_path) as img:
        w, h = img.size
    return h > w

def card_aspect_ratio(image_path: str) -> float:
    """
    방향과 무관하게 가로세로 비율을 1 이상으로 반환.
    (max / min) → 카드형이면 보통 1.3~1.9 구간.
    """
    with _open_exif_transposed(image_path) as img:
        w, h = img.size
    long_side, short_side = (w, h) if w >= h else (h, w)
    return long_side / max(1, short_side)

def is_card_aspect_ratio(image_path: str, min_ratio: float = 1.3, max_ratio: float = 2.2) -> bool:
    r = card_aspect_ratio(image_path)
    return (min_ratio <= r <= max_ratio)

def get_text_density(ocr_result, image_path: str) -> float:
    """
    텍스트 박스 총 면적 / 이미지 면적  → 0~1 사이의 밀도 값.
    """
    with _open_exif_transposed(image_path) as img:
        W, H = img.size
    if W == 0 or H == 0:
        return 0.0

    total_box_area = 0.0
    for box in (ocr_result[0] or []):
        pts = box[0]
        x0, y0 = pts[0]
        x2, y2 = pts[2]
        w, h = abs(x2 - x0), abs(y2 - y0)
        # 박스가 이미지 경계를 넘는 경우 방어
        w = max(0, min(w, W))
        h = max(0, min(h, H))
        total_box_area += (w * h)

    return float(total_box_area) / float(W * H)

def is_card_like_student(image_path: str, ocr_result) -> bool:
    """
    학생증 전용 카드형 판단:
    - 비율이 카드형 범위(1.3~2.2) 이거나
    - 텍스트 밀도 >= 0.02 (2% 이상)
    """
    aspect_ok = is_card_aspect_ratio(image_path)
    density = get_text_density(ocr_result, image_path)
    density_ok = density >= 0.02
    return aspect_ok or density_ok

# (하위 호환) 기존 이름이 이미 사용 중이면 아래 alias 유지
def is_card_like(image_path: str, ocr_result) -> bool:
    return is_card_like_student(image_path, ocr_result)
