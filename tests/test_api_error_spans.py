from types import SimpleNamespace

from member3_backend.api import input_spans


def test_spans_are_found_in_the_original_text():
    text = "Intro. **Born:** Delhi, 1869."
    claim = SimpleNamespace(text="Gandhi was born in Delhi.", start_char=7, end_char=29)
    assert input_spans(text, claim, [[19, 24]]) == [[17, 22]]          # "Delhi" in the input
    assert input_spans(text, claim, [[0, 25]]) == [[7, 29]]            # whole claim -> whole slice
    assert input_spans(text, claim, [[0, 6]]) == [[7, 29]]             # "Gandhi" not in the slice -> whole slice
