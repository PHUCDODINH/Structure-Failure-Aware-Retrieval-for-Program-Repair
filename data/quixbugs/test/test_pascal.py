import pytest
from load_testdata import load_json_testcases

if pytest.use_correct:
    from data.quixbugs.correct.pascal import pascal
else:
    from data.quixbugs.buggy.pascal import pascal


testdata = load_json_testcases(pascal.__name__)


@pytest.mark.parametrize("input_data,expected", testdata)
def test_pascal(input_data, expected):
    assert pascal(*input_data) == expected
