import pytest
from load_testdata import load_json_testcases

if pytest.use_correct:
    from data.quixbugs.correct.quicksort import quicksort
else:
    from data.quixbugs.buggy.quicksort import quicksort


testdata = load_json_testcases(quicksort.__name__)


@pytest.mark.parametrize("input_data,expected", testdata)
def test_quicksort(input_data, expected):
    assert quicksort(*input_data) == expected
