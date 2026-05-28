import pytest
from load_testdata import load_json_testcases

if pytest.use_correct:
    from data.quixbugs.correct.lcs_length import lcs_length
else:
    from data.quixbugs.buggy.lcs_length import lcs_length


testdata = load_json_testcases(lcs_length.__name__)


@pytest.mark.parametrize("input_data,expected", testdata)
def test_lcs_length(input_data, expected):
    assert lcs_length(*input_data) == expected
