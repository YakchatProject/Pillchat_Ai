from flask import Flask, request, jsonify
from utils.classifier import classify_image
from utils.ocr import extract_text

app = Flask(__name__)

@app.route("/classify", methods=["POST"])
def classify_route():
    image_file = request.files.get("image")
    if not image_file:
        return jsonify({"error": "이미지가 누락되었습니다."}), 400

    label = classify_image(image_file)
    return jsonify({"label": label}), 200

@app.route("/ocr", methods=["POST"])
def ocr_route():
    image_file = request.files.get("image")
    if not image_file:
        return jsonify({"error": "이미지가 누락되었습니다."}), 400

    text_list = extract_text(image_file)
    return jsonify({"text": text_list}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
