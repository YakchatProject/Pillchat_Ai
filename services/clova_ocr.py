import os
import uuid
import time
import json
import requests
from typing import Dict, List, Optional

class ClovaOCR:
    def __init__(self, api_url: str, secret_key: str, default_lang: str = "ko"):
        self.api_url = api_url.rstrip("/")             # 콘솔의 Invoke URL 전체
        self.secret_key = secret_key
        self.default_lang = default_lang

    def ocr(self, image_path: str, template_ids: Optional[List[str]] = None) -> List[List]:
        """
        Clova OCR(v2) 호출 -> PaddleOCR 유사 포맷으로 변환해서 반환
        반환 형식: [[ [bbox4], (text, conf) ], ... ] 를 한 번 더 리스트로 감싸 배치처럼 [[...]]
        """
        ext = os.path.splitext(image_path)[1].lower().lstrip(".") or "jpg"

        request_json: Dict = {
            "version": "V2",
            "requestId": str(uuid.uuid4()),
            "timestamp": int(round(time.time() * 1000)),
            "images": [{"format": ext, "name": "demo"}],
            # "lang": self.default_lang,  # 필요 시 사용
        }
        if template_ids:
            request_json["templateIds"] = template_ids

        payload = {"message": json.dumps(request_json).encode("utf-8")}
        headers = {"X-OCR-SECRET": self.secret_key}

        with open(image_path, "rb") as f:
            files = [("file", f)]
            try:
                resp = requests.post(self.api_url, headers=headers, data=payload, files=files, timeout=(10, 30))
            except requests.RequestException as e:
                raise RuntimeError(f"Clova OCR 요청 실패: {e}")

        if resp.status_code != 200:
            raise RuntimeError(f"Clova OCR API 호출 실패: {resp.status_code}, {resp.text}")

        clova_result = resp.json()
        return self._convert_to_paddle_format(clova_result)

    def _convert_to_paddle_format(self, clova_result: Dict) -> List[List]:
        """Clova fields -> Paddle 형식 [[[[x,y]...], ('text', conf)], ...]"""
        images = clova_result.get("images") or []
        if not images:
            return [[]]

        fields = images[0].get("fields") or []
        paddle = []
        for f in fields:
            text = f.get("inferText") or ""
            conf = float(f.get("inferConfidence") or 0.0)
            verts = (f.get("boundingPoly") or {}).get("vertices") or []
            if len(verts) < 4:
                continue
            bbox = [
                [verts[0].get("x", 0), verts[0].get("y", 0)],
                [verts[1].get("x", 0), verts[1].get("y", 0)],
                [verts[2].get("x", 0), verts[2].get("y", 0)],
                [verts[3].get("x", 0), verts[3].get("y", 0)],
            ]
            paddle.append([bbox, (text, conf)])
        return [paddle]
