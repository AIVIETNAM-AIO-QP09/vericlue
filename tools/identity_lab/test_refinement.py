from refinement import choose_reread, value_polygon


def field():
    return {"value": "original", "candidates": ["original"], "status": "review", "reasons": []}


def evidence(text, confidence=0.9):
    return {"text": text, "confidence": confidence}


def test_repeat_does_not_upgrade_to_verified():
    result = field()
    choose_reread(result, "nationality", [evidence("new"), evidence("new"), evidence("other")])
    assert result["value"] == "new"
    assert result["original_value"] == "original"
    assert result["status"] == "review"
    assert "original" in result["candidates"]


def test_single_and_low_confidence_read_not_selected():
    result = field()
    choose_reread(result, "nationality", [evidence("new"), evidence("new", 0.1)])
    assert result["value"] == "original"


def test_invalid_date_not_corrected_by_regex():
    result = field()
    choose_reread(result, "date_of_expiry", [evidence("02/0712031"), evidence("02/0712031")])
    assert result["value"] == "original"


def test_valid_date_reread_normalized():
    result = field()
    choose_reread(result, "date_of_expiry", [evidence("02/07/2031"), evidence("02/07/2031")])
    assert result["value"] == "2031-07-02"


def test_no_word_location_no_guessed_crop():
    assert value_polygon({"words": [], "word_regions": []}, "nationality") is None


def test_value_crop_starts_after_label():
    line = {
        "words": ["Nationality", ": ", "Example"],
        "word_regions": [
            [[0, 0], [100, 0], [100, 30], [0, 30]],
            [[100, 0], [120, 0], [120, 30], [100, 30]],
            [[120, 0], [200, 0], [200, 30], [120, 30]],
        ],
        "polygon": [[0, 0], [200, 0], [200, 30], [0, 30]],
    }
    polygon = value_polygon(line, "nationality")
    assert 110 < polygon[0][0] < 120
