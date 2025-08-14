import re

def extract_license_fields(lines: list[str], full_text: str) -> dict:
    name = ''
    license_no = ''
    issue_date = ''

    for line in lines:
        if '성명' in line:
            name_match = re.search(r'성명[:\s]*([가-힣]{2,4})', line)
            if name_match:
                name = name_match.group(1)

        if '면허번호' in line:
            license_match = re.search(r'면허번호[:\s]*([A-Z]?[0-9]{5,10})', line)
            if license_match:
                license_no = license_match.group(1)

        date_match = re.search(r'(19\d{2}|20\d{2})년\s?[0-9]{1,2}월\s?[0-9]{1,2}일', line)
        if date_match:
            issue_date = date_match.group()

    return {
        "name": name,
        "licenseNumber": license_no,
        "issueDate": issue_date
    }
