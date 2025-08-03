from paddleocr import draw_ocr
from PIL import Image

def visualize_ocr_result(image_path: str, ocr_result, save_path: str = "ocr_result.jpg"):
    image = Image.open(image_path).convert("RGB")

    boxes = [line[0] for line in ocr_result[0]]
    txts = [line[1][0] for line in ocr_result[0]]
    scores = [line[1][1] for line in ocr_result[0]]

    # 한글 폰트 경로를 지정해야 텍스트가 깨지지 않음
    annotated = draw_ocr(
        image, boxes, txts, scores,
        font_path="fonts/NanumGothic.ttf"  # ← 폰트 파일 경로 수정 가능
    )

    result_image = Image.fromarray(annotated)
    result_image.save(save_path)
    print(f"[🖼️ OCR 시각화 저장 완료] {save_path}")
