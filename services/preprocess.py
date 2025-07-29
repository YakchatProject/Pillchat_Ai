import cv2
import numpy as np


def preprocess_image(input_path: str) -> str:
    import cv2
    import numpy as np

    img = cv2.imread(input_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    blurred = gray

    binary = cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_MEAN_C,  
        cv2.THRESH_BINARY,
        25, 
        5    
    )

    processed = binary

    resized = cv2.resize(processed, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_LINEAR)

    output_path = input_path.replace(".", "_pre.")
    cv2.imwrite(output_path, resized)
    return output_path
