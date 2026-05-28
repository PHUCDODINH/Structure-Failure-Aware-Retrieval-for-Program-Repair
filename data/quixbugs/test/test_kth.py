import pytest
from load_testdata import load_json_testcases

if pytest.use_correct:
    from data.quixbugs.correct.kth import kth
else:
    from data.quixbugs.buggy.kth import kth


testdata = load_json_testcases(kth.__name__)


@pytest.mark.parametrize("input_data,expected", testdata)
def test_kth(input_data, expected):
    assert kth(*input_data) == expected
