import requests

def test_student_ocr():
    with open("tests/images/sample_student.jpg", "rb") as f:
        files = {"file": ("sample_student.jpg", f, "image/jpeg")}
        response = requests.post("http://localhost:8000/ocr/student", files=files)
        assert response.status_code == 200
        data = response.json()
        assert "fields" in data
        assert data["valid"] is True
        print(" 학생증 OCR 결과:", data)
