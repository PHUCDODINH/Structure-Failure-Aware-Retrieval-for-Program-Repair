import pytest
from load_testdata import load_json_testcases

if pytest.use_correct:
    from data.quixbugs.correct.kheapsort import kheapsort
else:
    from data.quixbugs.buggy.kheapsort import kheapsort


testdata = load_json_testcases(kheapsort.__name__)


@pytest.mark.parametrize("input_data,expected", testdata)
def test_kheapsort(input_data, expected):
    assert list(kheapsort(*input_data)) == expected
