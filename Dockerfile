# 베이스 이미지
FROM python:3.10-slim

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 생성
WORKDIR /app

# 코드 복사
COPY . /app

# 의존성 설치
RUN pip install --upgrade pip \
 && pip install -r requirements.txt

# 모델 학습 (선택적, 최초 1회만 실행하면 주석 가능)
# RUN python train_classifier.py

# Flask 서버 실행
CMD ["python", "app.py"]
