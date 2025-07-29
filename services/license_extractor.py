import re

def extract_license_fields(lines: list[str], full_text: str) -> dict:
    name = ''
    license_no = ''
    issue_date = ''

    merged_line = ' '.join(lines)

    # 면허번호
    license_match = re.search(r'(?:제)?\s?(\d{4,10})\s?호', merged_line)
    if license_match:
        license_no = license_match.group(1)

    # 발급일자: 3개 조각이 줄 단위로 떨어져 있을 경우 대응
    for i in range(len(lines) - 2):
        y, m, d = lines[i:i+3]
        if re.fullmatch(r'(19|20)\d{2}년', y) and re.fullmatch(r'\d{1,2}월', m) and re.fullmatch(r'\d{1,2}일', d):
            issue_date = f"{y} {m} {d}"
            break

    # 보조: 전체 텍스트에서 가장 늦은 연도의 날짜 추출
    if not issue_date:
        matches = re.findall(r'((19|20)\d{2})년\s?\d{1,2}월\s?\d{1,2}일', full_text)
        if matches:
            latest_year = max(matches, key=lambda x: int(x[0]))[0]
            match = re.search(rf'{latest_year}년\s?\d{{1,2}}월\s?\d{{1,2}}일', full_text)
            if match:
                issue_date = match.group()
                
    # 이름 정규식 기반 추출)
    name_match = re.search(r'성\s*명.*?([가-힣]{2,4})', full_text)

    if name_match:
        name = name_match.group(1)
    else:
        # 줄 단위 탐색: '성명'이 포함된 줄에서 후보 이름 추출
        for i in range(len(lines)):
            if '성명' in lines[i] or '성 명' in lines[i]:
                candidates = re.findall(r'[가-힣]{2,4}', lines[i])
                for cand in candidates:
                    if re.fullmatch(r'[가-힣]{2,4}', cand):
                        name = cand
                        break
            if name:
                break

        # 보조: 다음 줄의 깨진 조각 시도
        if not name:
            for i in range(len(lines) - 1):
                if '성명' in lines[i] or '성 명' in lines[i]:
                    candidate = re.sub(r'[^가-힣]', '', lines[i + 1])
                    if re.fullmatch(r'[가-힣]{2,4}', candidate):
                        name = candidate
                        break

    # 5. fallback: 블랙리스트 제외한 첫 의미 있는 단어
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
