from app.pii import scrub_text


def test_scrub_email() -> None:
    out = scrub_text("Email me at student@vinuni.edu.vn")
    assert "student@" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_common_vietnamese_phone_formats() -> None:
    phone_numbers = (
        "0901234567",
        "090 123 4567",
        "090.123.4567",
        "090-123-4567",
        "+84 90 123 4567",
    )

    for phone_number in phone_numbers:
        out = scrub_text(f"Contact: {phone_number}")
        assert phone_number not in out
        assert "REDACTED_PHONE_VN" in out


def test_scrub_existing_identity_and_payment_patterns() -> None:
    out = scrub_text("CCCD 012345678901, card 4111 1111 1111 1111")

    assert "012345678901" not in out
    assert "4111 1111 1111 1111" not in out
    assert "REDACTED_CCCD" in out
    assert "REDACTED_CREDIT_CARD" in out


def test_scrub_vietnamese_passport() -> None:
    out = scrub_text("Passport: B1234567")

    assert "B1234567" not in out
    assert "REDACTED_PASSPORT" in out


def test_passport_pattern_does_not_scrub_invalid_values() -> None:
    for value in ("b1234567", "B123456", "AB1234567", "B12345678"):
        assert value in scrub_text(f"Reference: {value}")


def test_scrub_labeled_vietnamese_address() -> None:
    messages = (
        "Địa chỉ: 123 Nguyễn Trãi, Quận 1",
        "DIA CHI: 45 Le Loi, Quan 3",
    )

    for message in messages:
        out = scrub_text(message)
        assert message not in out
        assert "REDACTED_ADDRESS_VN" in out


def test_address_pattern_does_not_scrub_unlabeled_location_text() -> None:
    text = "Giao hàng trên đường Nguyễn Trãi"

    assert scrub_text(text) == text
