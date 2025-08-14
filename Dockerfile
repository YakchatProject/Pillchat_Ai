# 베이스 이미지
FROM python:3.10-slim

# 시스템 의존성 설치 (OpenCV용)
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 생성
WORKDIR /app

# 환경 변수 파일 복사
COPY .env* /app/

# requirements.txt 먼저 복사 (캐시 최적화)
COPY requirements.txt /app/

# 의존성 설치
RUN pip install --upgrade pip \
 && pip install -r requirements.txt

# 코드 복사
COPY . /app

# 환경 변수 로드
ENV PYTHONPATH=/app

# FastAPI 서버 실행 (main.py 기준)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]