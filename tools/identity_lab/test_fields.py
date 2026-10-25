from fields import extract_fields, value_for


def line(text, alternate, x, y, width=180):
    return {
        "text": text,
        "alternate_text": alternate,
        "confidence": 0.9,
        "alternate_confidence": 0.9,
        "polygon": [[x, y], [x + width, y], [x + width, y + 30], [x, y + 30]],
    }


def test_invalid_date_and_long_id():
    assert value_for("31/02/2030", "date_of_expiry") == []
    assert value_for("1234567890123", "id_number") == []


def test_address_continuation_preserves_both_readers():
    fields = extract_fields(
        [
            line(
                "Nơi thường trú / Place of residence: A12",
                "Nơi thường trú / Place of residence: A13",
                500,
                100,
                600,
            ),
            line("Phường Một, Thành phố Hai", "Phường Mot, Thành phố Hai", 500, 140, 600),
        ]
    )
    address = fields["place_of_residence"]
    assert address["status"] == "review"
    assert address["source_line_ids"] == [0, 1]
    assert len(address["candidates"]) == 2
    assert address["value"].endswith("Thành phố Hai")


def test_vietnamese_only_sex_prefix():
    assert value_for("Nam Quốc tịch Việt Nam", "sex") == ["Nam"]


def test_expiry_single_reader_kept_for_review():
    fields = extract_fields([line("Có giá trị đến 02/0712031", "Có giá trị đến 02/07/2031", 0, 0)])
    assert fields["date_of_expiry"]["value"] == "2031-07-02"
    assert fields["date_of_expiry"]["status"] == "review"


def test_noise_does_not_poison_id():
    fields = extract_fields(
        [
            line("Số I No.", "Số / No.", 0, 100),
            line("123456789012", "123456789012", 200, 100),
            line("DILLED", "00", 900, 0),
        ]
    )
    assert fields["id_number"]["status"] == "consistent"


def test_two_valid_ids_conflict():
    fields = extract_fields(
        [line("Số / No.", "Số / No.", 0, 0), line("123456789012", "123456789013", 200, 0)]
    )
    assert fields["id_number"]["status"] == "review"
    assert len(fields["id_number"]["candidates"]) == 2


def test_merged_sex_nationality():
    fields = extract_fields(
        [
            line("Giới tính / Sex", "Giới tính / Sex", 0, 0),
            line(
                "Nam Quốc tịch / Nationality: Việt Nam",
                "Nam Quốc tịch / Nationality: Việt Nam",
                200,
                0,
            ),
        ]
    )
    assert fields["sex"]["value"] == "Nam"
    assert fields["nationality"]["value"] == "Việt Nam"


def test_missing_and_unlabelled_dates_not_guessed():
    fields = extract_fields([line("01/01/2000", "01/01/2000", 0, 0)])
    assert fields["date_of_birth"]["status"] == "missing"
    assert fields["date_of_expiry"]["status"] == "missing"


def test_expiry_before_birth_flagged():
    fields = extract_fields(
        [
            line("Ngày sinh 01/01/2000", "Ngày sinh 01/01/2000", 0, 0),
            line("Có giá trị đến 01/01/1999", "Có giá trị đến 01/01/1999", 0, 300),
        ]
    )
    assert "EXPIRY_NOT_AFTER_BIRTH" in fields["date_of_expiry"]["reasons"]
