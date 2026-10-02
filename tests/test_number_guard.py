"""Number guard (member3_backend/number_guard.py): a passage supports a claim only if it
contains the claim's numbers. Cases measured live before the guard: all three false claims
below were Verified."""
from member3_backend.number_guard import missing_numbers, numbers

INDEPENDENCE = "India gained independence on 15 August 1947 from the United Kingdom."
EVEREST = "Its elevation of 8,848.86 m was most recently established in 2020."


def test_numbers_are_read_in_every_common_form():
    assert numbers("8,849 m (8,848.86)") == [(8849.0, 0), (8848.86, 2)]
    assert [v for v, _ in numbers("eleven players, twenty-one guns, १९४७")] == [1947.0, 11.0, 21.0]
    assert numbers("Chandrayaan-3 and COVID-19 in the 21st century") == []  # names and ordinals


def test_wrong_numbers_are_missing_from_the_evidence():
    assert missing_numbers("India became independent in 1950.", INDEPENDENCE) == ["1950"]
    assert missing_numbers("Mount Everest is 7,200 metres tall.", EVEREST) == ["7200"]
    assert missing_numbers("It came into effect on 15 August 1947.", "It came into effect on 26 January 1950.") == [
        "15", "1947"]


def test_right_numbers_match_however_they_are_written():
    assert missing_numbers("India became independent in 1947.", INDEPENDENCE) == []
    assert missing_numbers("Mount Everest is 8,849 metres tall.", EVEREST) == []  # rounded
    assert missing_numbers("Cricket has 11 players per team.", "two teams of eleven players each") == []
    assert missing_numbers("India has about 1.4 billion people.", "about 1.43 billion people") == []
    assert missing_numbers("India has about 2 billion people.", "about 1.43 billion people") == ["2"]
    assert missing_numbers("भारत 1947 में स्वतंत्र हुआ।", "भारत १९४७ में स्वतंत्र हुआ") == []
    assert missing_numbers("The Taj Mahal is a monument.", "anything") == []  # no numbers: nothing to check
