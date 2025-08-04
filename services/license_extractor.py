import re
from datetime import datetime

def extract_issue_date_from_ocr(words: list[str], full_text: str) -> str:
    candidates = []

    # 단어 3조각 기반으로 가능한 모든 날짜 후보 탐색
    for i in range(len(words) - 2):
        y, m, d = words[i:i+3]
        if re.fullmatch(r'(19|20)\d{2}년', y) and re.fullmatch(r'\d{1,2}월', m) and re.fullmatch(r'\d{1,2}일', d):
            date_str = f"{y} {m} {d}"
            try:
                dt = datetime.strptime(date_str, "%Y년 %m월 %d일")
                candidates.append(dt)
            except ValueError:
                continue

    # 후보 중 가장 최근 날짜 선택
    if candidates:
        latest = max(candidates)
        issue_date = latest.strftime('%Y년 %m월 %d일')
        return issue_date

    return ''


def extract_license_fields(lines: list[str], full_text: str) -> dict:
    name = ''
    license_no = ''
    issue_date = ''

    merged_line = ' '.join(lines)

    # 1. 면허번호
    license_match = re.search(r'(?:제)?\s?(\d{4,10})\s?호', merged_line)
    if license_match:
        license_no = license_match.group(1)

    # 2. 발급일자 (단어 리스트 기준 개선)
    issue_date = extract_issue_date_from_ocr(lines, full_text)

    # 3. 이름 추출
    name_match = re.search(r'성\s*명.*?([가-힣]{2,4})', full_text)
    if name_match:
        name = name_match.group(1)
    else:
        # 줄 단위에서 '성명' 포함된 줄 처리
        for i in range(len(lines)):
            if '성명' in lines[i] or '성 명' in lines[i]:
                candidates = re.findall(r'[가-힣]{2,4}', lines[i])
                for cand in candidates:
                    if re.fullmatch(r'[가-힣]{2,4}', cand):
                        name = cand
                        break
            if name:
                break

        # 다음 줄 깨짐 보조 처리
        if not name:
            for i in range(len(lines) - 1):
                if '성명' in lines[i] or '성 명' in lines[i]:
                    candidate = re.sub(r'[^가-힣]', '', lines[i + 1])
                    if re.fullmatch(r'[가-힣]{2,4}', candidate):
                        name = candidate
                        break

    # 4. fallback 이름 추출 (블랙리스트 제외)
    if not name and any(k in full_text for k in ['성명', '성 명']):
        blacklist = {
            '같이', '면허증', '보건복지부', '보건복제부칭', '금거', '제', '중6', '국장', '교국',
            '조항', 'HEALT', '3조', '3근', '명일', '눔교국', '성명', '년', '월', '일', '약사범'
        }
        for token in re.findall(r'[가-힣]{2,4}', full_text):
            if token not in blacklist:
                name = token
                break

    return {
        "name": name,
        "licenseNumber": license_no,
        "issueDate": issue_date
    }
