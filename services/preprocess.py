import cv2
import numpy as np

def preprocess_image(input_path: str) -> str:
    import cv2
    img = cv2.imread(input_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 안정형 CLAHE
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    
    binary = cv2.adaptiveThreshold(
        enhanced, 255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY, 11, 2
    )

    resized = cv2.resize(binary, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)

    output_path = input_path.replace(".", "_pre.")
    cv2.imwrite(output_path, resized)
    return output_path
