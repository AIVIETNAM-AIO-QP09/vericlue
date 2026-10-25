from field_recognition import normalized_value, recognize_field, select_reading
from PIL import Image


def reading(text, confidence=0.9):
    return {"text": text, "confidence": confidence, "variant": "test"}


def test_dates_are_validated_not_repaired():
    assert normalized_value("expire_date", "02/0712031") is None
    assert normalized_value("dob", "31/02/2001") is None
    assert normalized_value("dob", "02/07/2001") == "2001-07-02"


def test_invalid_date_needs_stable_reread():
    result = select_reading("expire_date", [reading("02/0712031"), reading("02/07/2031")])
    assert result["text"] is None
    result = select_reading(
        "expire_date", [reading("02/0712031"), reading("02/07/2031"), reading("02/07/2031")]
    )
    assert result["text"] == "02/07/2031"
    assert result["status"] == "review"
    assert result["original_text"] == "02/0712031"


def test_no_guessed_address_correction_or_low_confidence_vote():
    result = select_reading(
        "current_place1", [reading("D5381"), reading("D538i", 0.2), reading("D538i", 0.3)]
    )
    assert result["text"] == "D5381"
    assert "READINGS_DISAGREE" in result["reasons"]


def test_free_text_majority_does_not_overwrite_original():
    result = select_reading(
        "current_place2", [reading("Biên Hòa"), reading("Biên Hoa"), reading("Biên Hoa")]
    )
    assert result["text"] == "Biên Hòa"
    assert result["suggested_text"] == "Biên Hoa"


def test_crop_at_image_edge_and_evidence_saved(tmp_path):
    class Reader:
        def predict(self, image, return_prob):
            assert min(image.size) > 0
            return "02/07/2031", 0.9

    result = recognize_field(
        Image.new("RGB", (100, 20), "white"),
        (0, 0, 100, 20),
        "expire_date",
        Reader(),
        tmp_path,
        "expiry",
    )
    assert len(result["readings"]) == 7
    assert result["normalized_value"] == "2031-07-02"
    for reading in result["readings"]:
        assert (tmp_path / reading["crop"]).exists()
        assert reading["source_box"] == [0, 0, 100, 20]
