import re

def find_line_with_prefix(lines, prefixes):
    for line in lines:
        for prefix in prefixes:
            if line.startswith(prefix):
                return line.replace(prefix, '').strip()
    return ''

def extract_name_from_lines(lines):
    return find_line_with_prefix(lines, ['이름:', '성명:', 'Name:', 'NAME'])

def extract_student_id_from_lines(lines):
    return find_line_with_prefix(lines, ['학번:', 'Student ID:', 'ID:'])

def extract_birth_from_lines(lines):
    raw = find_line_with_prefix(lines, ['생년월일:', 'Birth:', 'DOB:', '출생일:'])
    if re.fullmatch(r'\d{8}', raw):
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    return raw

def extract_university_from_lines(lines):
    for line in lines:
        if '대학교' in line:
            return line.strip()
    return ''

def extract_name_regex(text):
    candidates = re.findall(r'\b[가-힣]{2,4}\b', text)
    for word in candidates:
        if '대학교' not in word and '학과' not in word:
            return word
    return ''

def extract_student_id_regex(text):
    match = re.search(r'\b\d{8,10}\b', text)
    return match.group() if match else ''

def extract_birth_regex(text):
    match = re.search(r'\b(19\d{2}|20\d{2})[-.]?(0[1-9]|1[0-2])[-.]?(0[1-9]|[12]\d|3[01])\b', text)
    if match:
        raw = match.group()
        return raw if '-' in raw else f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    return ''

def extract_university_regex(text):
    match = re.search(r'[가-힣]+대학교', text)
    return match.group() if match else ''

def extract_all_fields_from_lines(lines: list[str]) -> dict:
    full_text = ' '.join(lines)
    return {
        "name": extract_name_from_lines(lines) or extract_name_regex(full_text),
        "studentId": extract_student_id_from_lines(lines) or extract_student_id_regex(full_text),
        "birthDate": extract_birth_from_lines(lines) or extract_birth_regex(full_text),
        "university": extract_university_from_lines(lines) or extract_university_regex(full_text),
    }
