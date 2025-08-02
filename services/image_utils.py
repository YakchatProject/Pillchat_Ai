
from PIL import Image

def is_vertical_card(image_path: str) -> bool:
    img = Image.open(image_path)
    width, height = img.size
    return height > width


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

