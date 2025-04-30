from paddleocr import PaddleOCR
from PIL import Image
import io

# OCR 엔진 초기화 (한국어 + 각도 보정 활성화)
ocr_engine = PaddleOCR(use_angle_cls=True, lang='korean')

def extract_text(file):

    image = Image.open(file.stream).convert("RGB")
    image_byte_array = io.BytesIO()
    image.save(image_byte_array, format='PNG')
    image_data = image_byte_array.getvalue()

    result = ocr_engine.ocr(image_data, cls=True)
    texts = [line[1][0] for line in result[0]] if result and result[0] else []
    return texts
