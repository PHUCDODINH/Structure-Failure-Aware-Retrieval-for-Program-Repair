import pytest
from load_testdata import load_json_testcases

if pytest.use_correct:
    from data.quixbugs.correct.wrap import wrap
else:
    from data.quixbugs.buggy.wrap import wrap


testdata = load_json_testcases(wrap.__name__)


@pytest.mark.parametrize("input_data,expected", testdata)
def test_wrap(input_data, expected):
    assert wrap(*input_data) == expected
