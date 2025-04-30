
from PIL import Image
import io

def preprocess_image(file, target_size=(224, 224)):
    # 업로드된 이미지 파일을 Pillow Image로 변환 후 크기 조정
    image = Image.open(file.stream).convert("RGB")
    image = image.resize(target_size)
    return image
