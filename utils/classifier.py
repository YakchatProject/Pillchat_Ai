import torch
from torchvision import models, transforms
from PIL import Image
from utils.preprocess import preprocess_image

LABELS = ["student_id", "pharmacist_license", "other"]

# 모델 정의 (state_dict 로드용)
def load_model():
    model = models.resnet18(pretrained=False)
    model.fc = torch.nn.Linear(model.fc.in_features, len(LABELS))
    model.load_state_dict(torch.load("model/classifier.pt", map_location="cpu"))
    model.eval()
    return model

model = load_model()

# 입력 이미지 전처리 파이프라인
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
])

def classify_image(file):
    image = preprocess_image(file)  # 예: PIL.Image
    image_tensor = transform(image).unsqueeze(0)  # (1, C, H, W)

    with torch.no_grad():
        outputs = model(image_tensor)
        predicted_idx = torch.argmax(outputs, dim=1).item()

    return LABELS[predicted_idx]
