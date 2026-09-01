import re

def clean_extracted_text(text: str) -> str:
    """Normalize whitespace and remove non-printable characters."""
    if not text:
        return ""
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def extract_claim_id(text: str) -> str:
    """Extract CLM-YYYY-XXXX format claim reference."""
    match = re.search(r"CLM-\d{4}-\d{4}", text)
    return match.group(0) if match else "UNKNOWN"