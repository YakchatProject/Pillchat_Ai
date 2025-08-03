from paddleocr import PaddleOCR

def create_ocr_model(rec_image_shape: str) -> PaddleOCR:
    return PaddleOCR(
        use_angle_cls=True,
        lang='korean',
        det_db_box_thresh=0.2,
        det_db_unclip_ratio=2.0,
        drop_score=0.25,
        rec_algorithm='CRNN',
        rec_image_shape=rec_image_shape,
        max_text_length=30
    )

