import pytest
from load_testdata import load_json_testcases

if pytest.use_correct:
    from data.quixbugs.correct.is_valid_parenthesization import is_valid_parenthesization
else:
    from data.quixbugs.buggy.is_valid_parenthesization import is_valid_parenthesization


testdata = load_json_testcases(is_valid_parenthesization.__name__)


@pytest.mark.parametrize("input_data,expected", testdata)
def test_is_valid_parenthesization(input_data, expected):
    assert is_valid_parenthesization(*input_data) == expected
