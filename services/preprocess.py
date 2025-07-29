import cv2
import numpy as np


def preprocess_image(input_path: str) -> str:

    img = cv2.imread(input_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY)

    # 너무 크면 느림 → 1.5배 확대 정도로만
    resized = cv2.resize(binary, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_LINEAR)

    output_path = input_path.replace(".", "_pre.")
    cv2.imwrite(output_path, resized)
    return output_path