from paddleocr import PaddleOCR

def create_ocr_model(rec_image_shape: str = '3, 32, 320') -> PaddleOCR:
    return PaddleOCR(
        use_angle_cls=True,
        lang='korean',
        det_db_box_thresh=0.6,
        det_db_unclip_ratio=1.5,
        drop_score=0.4,
        rec_algorithm='CRNN',
        rec_image_shape=rec_image_shape,
        max_text_length=30
    )

