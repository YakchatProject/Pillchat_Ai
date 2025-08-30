import os
import uuid
import time
import json
import requests
from typing import Dict, List, Optional, Tuple

class ClovaOCR:
    def __init__(
        self,
        api_url: str,
        secret_key: str,
        default_lang: str = "ko",
        connect_timeout: int = 10,
        read_timeout: int = 30,
        max_retries: int = 2,
    ):
        self.api_url = api_url.rstrip("/")
        self.secret_key = secret_key
        self.default_lang = default_lang
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.max_retries = max_retries
        if not self.api_url or not self.secret_key:
            raise ValueError("Clova OCR 설정(api_url/secret_key)이 비어 있습니다.")

    def ocr(self, image_path: str, template_ids: Optional[List[str]] = None, lang: Optional[str] = None) -> List[List]:
        """
        Clova OCR(v2) 호출 → PaddleOCR 유사 포맷 반환
        반환: [ [ [bbox4], (text, conf) ], ... ] 를 한 번 더 감싼 [[...]]
        """
        ext = (os.path.splitext(image_path)[1].lower().lstrip(".") or "jpg")
        request_json: Dict = {
            "version": "V2",
            "requestId": str(uuid.uuid4()),
            "timestamp": int(round(time.time() * 1000)),
            "images": [{"format": ext, "name": "demo"}],
        }
        # 언어/템플릿 옵션
        if template_ids:
            request_json["templateIds"] = template_ids
        if (lang or self.default_lang) and (lang or self.default_lang) != "auto":
            request_json["lang"] = lang or self.default_lang

        payload = {"message": json.dumps(request_json).encode("utf-8")}
        headers = {"X-OCR-SECRET": self.secret_key}

        # 간단 재시도
        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                with open(image_path, "rb") as f:
                    files = [("file", f)]
                    resp = requests.post(
                        self.api_url,
                        headers=headers,
                        data=payload,
                        files=files,
                        timeout=(self.connect_timeout, self.read_timeout),
                    )
                if resp.status_code == 200:
                    clova_result = resp.json()
                    return self._convert_to_paddle_format(clova_result)
                else:
                    # 4xx는 즉시 실패, 5xx는 재시도
                    msg = f"Clova OCR API 실패[{resp.status_code}]: {resp.text[:200]}"
                    if 500 <= resp.status_code < 600 and attempt < self.max_retries:
                        time.sleep(0.6 * (attempt + 1))
                        continue
                    raise RuntimeError(msg)
            except (requests.Timeout, requests.ConnectionError) as e:
                last_err = e
                if attempt < self.max_retries:
                    time.sleep(0.6 * (attempt + 1))
                    continue
                raise RuntimeError(f"Clova OCR 네트워크 오류: {e}")
            except requests.RequestException as e:
                raise RuntimeError(f"Clova OCR 요청 실패: {e}")
        # 여기 오면 전부 실패
        raise RuntimeError(f"Clova OCR 요청 반복 실패: {last_err}")

    def _convert_to_paddle_format(self, clova_result: Dict) -> List[List]:
        """
        Clova 응답 -> Paddle 형식 [[[[x,y]...], ('text', conf)], ...]
        - images[0].fields[*].inferText / inferConfidence / boundingPoly.vertices 기준
        """
        images = clova_result.get("images") or []
        if not images:
            return [[]]

        fields = images[0].get("fields") or []
        paddle = []
        for f in fields:
            text = f.get("inferText") or ""
            # 일부 응답엔 inferConfidence가 문자열일 수 있어 float 캐스팅
            try:
                conf = float(f.get("inferConfidence") or 0.0)
            except (TypeError, ValueError):
                conf = 0.0
            verts = (f.get("boundingPoly") or {}).get("vertices") or []
            if len(verts) < 4:
                # 누락/이상값 방어
                continue
            bbox = [
                [int(verts[0].get("x", 0)), int(verts[0].get("y", 0))],
                [int(verts[1].get("x", 0)), int(verts[1].get("y", 0))],
                [int(verts[2].get("x", 0)), int(verts[2].get("y", 0))],
                [int(verts[3].get("x", 0)), int(verts[3].get("y", 0))],
            ]
            paddle.append([bbox, (text, conf)])
        return [paddle]

    # 헬퍼: 상위 로직에서 빠르게 라인 리스트만 쓰고 싶을 때
    def ocr_lines(self, image_path: str, conf_min: float = 0.7) -> List[str]:
        """
        OCR → conf >= conf_min 만 골라 Y순 정렬 후 텍스트 라인 리스트 반환
        (정밀한 병합은 서비스 레벨에서 처리)
        """
        result = self.ocr(image_path)
        items = [b for b in result[0] if float(b[1][1]) >= conf_min]
        # Y 중심 기준 정렬
        def _ycenter(b):
            y1 = b[0][0][1]
            y3 = b[0][2][1]
            return (y1 + y3) / 2
        items.sort(key=_ycenter)
        return [b[1][0] for b in items]
