import pytest
from prepare_fgnet import parse_name, select_roles


def test_parse_filename_labels_not_inferred_age():
    assert parse_name("078A11.JPG") == ("fgnet_078", 11)
    assert parse_name("001A21a.jpg") == ("fgnet_001", 21)
    with pytest.raises(ValueError):
        parse_name("../../oops.jpg")


def test_age_roles_exclude_minors_and_guarantee_three_year_gap():
    rows = [
        {"identity": person, "age": age, "file": f"{person}-{age}"}
        for person, ages in [("p1", [17, 18, 20, 21, 30]), ("p2", [18, 19]), ("p3", [20, 25])]
        for age in ages
    ]
    selected = select_roles(rows)
    assert {r["identity"] for r in selected} == {"p1", "p3"}
    assert all(r["age"] >= 18 for r in selected)
    for person in ["p1", "p3"]:
        early = [r["age"] for r in selected if r["identity"] == person and r["role"] == "reference"]
        later = [r["age"] for r in selected if r["identity"] == person and r["role"] == "selfie"]
        assert min(later) - max(early) >= 3
    assert select_roles(rows[::-1]) != []
