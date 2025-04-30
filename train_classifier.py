import torch
import torch.nn as nn
from torchvision import datasets, transforms, models
from torch.utils.data import DataLoader, random_split
import os

# 하이퍼파라미터
BATCH_SIZE = 16
EPOCHS = 10
LR = 1e-4
DATA_DIR = "./dataset"
MODEL_PATH = "./model/classifier.pt"
CLASS_PATH = "./model/classes.txt"

# 이미지 전처리 파이프라인
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
])

# 데이터셋 로드 (폴더명 = 클래스 라벨)
full_dataset = datasets.ImageFolder(root=DATA_DIR, transform=transform)

# 클래스 정보 저장
os.makedirs(os.path.dirname(CLASS_PATH), exist_ok=True)
with open(CLASS_PATH, "w") as f:
    f.write("\n".join(full_dataset.classes))
print(f"클래스: {full_dataset.classes}")

# train / val 분리
train_size = int(0.8 * len(full_dataset))
val_size = len(full_dataset) - train_size
train_dataset, val_dataset = random_split(full_dataset, [train_size, val_size])

train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE)

# Pretrained ResNet18 + Custom FC Layer
num_classes = len(full_dataset.classes)
model = models.resnet18(pretrained=True)
model.fc = nn.Linear(model.fc.in_features, num_classes)

# 학습 설정
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = model.to(device)
criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.parameters(), lr=LR)

# 학습 루프
for epoch in range(EPOCHS):
    model.train()
    total_loss = 0
    for images, labels in train_loader:
        images, labels = images.to(device), labels.to(device)
        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
    print(f"[Epoch {epoch+1}] Train Loss: {total_loss:.4f}")

    # 간단한 validation loss 출력
    model.eval()
    val_loss = 0
    correct = 0
    with torch.no_grad():
        for images, labels in val_loader:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            loss = criterion(outputs, labels)
            val_loss += loss.item()
            preds = torch.argmax(outputs, dim=1)
            correct += (preds == labels).sum().item()
    accuracy = correct / len(val_dataset)
    print(f"           Val Loss: {val_loss:.4f}, Acc: {accuracy:.2%}")

# 모델 저장 (state_dict 방식)
os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
torch.save(model.state_dict(), MODEL_PATH)
print(f"모델 저장 완료: {MODEL_PATH}")
