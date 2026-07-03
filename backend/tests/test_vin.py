from app.ml.postprocess.vin import (
    extract_serials,
    extract_vin_candidates,
    is_valid_vin,
)


def test_valid_vin_checksum():
    assert is_valid_vin("1HGBH41JXMN109186")  # canonical valid VIN


def test_invalid_check_digit():
    assert not is_valid_vin("1HGBH41J1MN109186")  # wrong check digit


def test_rejects_illegal_chars_and_length():
    assert not is_valid_vin("1HGBH41JIMN109186")  # contains I
    assert not is_valid_vin("SHORT")


def test_extract_vin_prefers_valid():
    text = "Plate reads 1HGBH41JXMN109186 near the frame."
    cands = extract_vin_candidates(text)
    assert cands and cands[0] == "1HGBH41JXMN109186"


def test_extract_vin_not_glued_to_adjacent_text():
    # Regression: stripping spaces used to glue trailing text onto the VIN.
    assert "1HGBH41JXMN109186" in extract_vin_candidates("vin:1HGBH41JXMN109186 OK")


def test_extract_serials_excludes_vin():
    serials = extract_serials("MOTOR SN MTR12345 VIN 1HGBH41JXMN109186")
    assert "MTR12345" in serials
    assert "1HGBH41JXMN109186" not in serials
