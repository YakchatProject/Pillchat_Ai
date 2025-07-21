import requests

def test_professional_ocr():
    with open("tests/images/sample_license.jpg", "rb") as f:
        files = {"file": ("sample_license.jpg", f, "image/jpeg")}
        response = requests.post("http://localhost:8000/ocr/professional", files=files)
        assert response.status_code == 200
        data = response.json()
        assert "fields" in data
        assert data["valid"] is True
        print(" 면허증 OCR 결과:", data)
