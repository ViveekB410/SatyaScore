"""Number guard (member3_backend/number_guard.py, version 2): the evidence must contain the
claim's years and numbers of 100 or more. Cases measured live before the guard: all three
false claims below were Verified."""
from member3_backend.number_guard import checked_numbers, missing_numbers, numbers

INDEPENDENCE = "India gained independence on 15 August 1947 from the United Kingdom."
EVEREST = "Its elevation of 8,848.86 m was most recently established in 2020."


def test_numbers_are_read_in_every_common_form():
    assert numbers("8,849 m (8,848.86)") == [(8849.0, 0), (8848.86, 2)]
    assert [v for v, _ in numbers("eleven players, twenty-one guns, १९४७")] == [1947.0, 11.0, 21.0]
    assert [v for v, _ in numbers("४,३०,००० and 29,97,92,458")] == [430000.0, 299792458.0]  # Indian grouping
    assert numbers("Chandrayaan-3 and COVID-19 in the 21st century") == []  # names and ordinals


def test_only_years_and_large_digit_numbers_are_checked():
    # attempt 1 checked these and wrongly removed Verified from true claims
    for claim in ("He is one of the greatest Mughal emperors.", "There are two main types of stroke.",
                  "India has won 8 Olympic gold medals in hockey.", "२) प्रतिरक्षा कोशिकाएं वायरस को नष्ट करती हैं।",
                  "Article 370 gave the state special status.", "यह आयोग अनुच्छेद 324 के तहत स्थापित है।"):
        assert checked_numbers(claim) == [], claim
    assert checked_numbers("India became independent on 15 August 1947.") == [(1947.0, 0, True)]
    assert checked_numbers("about 1,400 million") == [(1400.0, -2, False)]  # commas: not a year


def test_wrong_numbers_are_missing_from_the_evidence():
    assert missing_numbers("India became independent in 1950.", INDEPENDENCE) == ["1950"]
    assert missing_numbers("Mount Everest is 7,200 metres tall.", EVEREST) == ["7200"]
    assert missing_numbers("It came into effect on 15 August 1947.", "It came into effect on 26 January 1950.") == [
        "1947"]


def test_right_numbers_match_however_they_are_written_and_wherever_in_the_article():
    assert missing_numbers("India became independent in 1947.", INDEPENDENCE) == []
    assert missing_numbers("Mount Everest is 8,849 metres tall.", EVEREST) == []  # rounded
    assert missing_numbers("India has about 1,400 million people.", "about 1,430 million people") == []  # round number
    assert missing_numbers("India has about 2,000 million people.", "about 1,430 million people") == ["2000"]
    assert missing_numbers("The road is 100 km long.", "The road is 140 km long.") == ["100"]
    assert missing_numbers("इसका क्षेत्रफल ४,३०,००० वर्ग किलोमीटर है।", "430,000 square kilometres") == []
    assert missing_numbers("भारत 1947 में स्वतंत्र हुआ।", "भारत १९४७ में स्वतंत्र हुआ") == []
    # the year is in another passage of the same article (the pipeline passes all of them)
    assert missing_numbers("The assembly met from 1947 to 1949.", ["The assembly first met in 1946.",
                                                                   "It worked from 1947 to 1949."]) == []

def test_review_findings_reference_words_and_years_on_the_evidence_side():
    # "no" inside "Nagano" is not the reference word "No." (the year must still be checked)
    assert checked_numbers("The Nagano 1998 Winter Olympics began in February.") == [(1998.0, 0, True)]
    assert checked_numbers("Article no. 370 was revoked.") == []
    # a claim's quantity does not match an unrelated YEAR in the article
    # (1,500 rounds to the nearest hundred, so the year 1520 would have matched)
    assert missing_numbers("The road is 1,500 km long.", "The road was first built in 1520.") == ["1500"]
    assert missing_numbers("The road is 1,500 km long.", "The road is 1,500 km long.") == []
