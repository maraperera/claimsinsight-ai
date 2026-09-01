import pytest
from src.pipeline_utils.text_cleaner import clean_extracted_text, extract_claim_id

def test_extract_claim_id_valid():
    sample = "Patient Allison Hill Associated Claim: CLM-2026-1000 Status: ACTIVE"
    assert extract_claim_id(sample) == "CLM-2026-1000"

def test_extract_claim_id_missing():
    sample = "No identifier provided in header."
    assert extract_claim_id(sample) == "UNKNOWN"

def test_clean_extracted_text():
    dirty_text = "Line 1\r\n\r\n\r\n\r\nLine 2   \n"
    expected = "Line 1\n\nLine 2"
    assert clean_extracted_text(dirty_text) == expected

def test_clean_extracted_text_empty():
    assert clean_extracted_text("") == ""