from recognizer_comparison import compare_readers


def test_disagreement_abstains_without_guessing():
    result = compare_readers(
        "current_place1", {"text": "X1231", "recognition_score": 0.9}, "X123i", 0.9
    )
    assert result["value"] is None
    assert result["candidate_text"] == "X1231"
    assert result["comparison_text"] == "X123i"


def test_agreement_remains_review_and_dates_normalize():
    result = compare_readers(
        "dob", {"text": "15/08/2000", "recognition_score": 0.9}, "15-08-2000", 0.9
    )
    assert result["value"] == "2000-08-15"
    assert result["status"] == "review"


def test_low_confidence_is_not_verified_by_matching_text():
    result = compare_readers("name", {"text": "ABC", "recognition_score": 0.2}, "ABC", 0.9)
    assert result["value"] is None
