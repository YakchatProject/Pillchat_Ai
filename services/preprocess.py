import cv2
import numpy as np

def preprocess_image(input_path: str) -> str:
    img = cv2.imread(input_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # ✅ 대비 과하지 않은 CLAHE (부드러운 enhancement)
    clahe = cv2.createCLAHE(clipLimit=1.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # ✅ 강한 이진화 대신 밝기 보정만
    normalized = cv2.normalize(enhanced, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX)

    # ✅ 블러로 노이즈 살짝 제거 (이진화 아님)
    blurred = cv2.GaussianBlur(normalized, (1, 1), 0)

    # ✅ 선명하게 확대 (1.3배, 선형)
    resized = cv2.resize(blurred, None, fx=1.3, fy=1.3, interpolation=cv2.INTER_LINEAR)

    output_path = input_path.replace(".", "_pre_soft.")
    cv2.imwrite(output_path, resized)
    return output_path
