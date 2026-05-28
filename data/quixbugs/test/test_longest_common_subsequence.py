import pytest
from load_testdata import load_json_testcases

if pytest.use_correct:
    from data.quixbugs.correct.longest_common_subsequence import longest_common_subsequence
else:
    from data.quixbugs.buggy.longest_common_subsequence import longest_common_subsequence


testdata = load_json_testcases(longest_common_subsequence.__name__)


@pytest.mark.parametrize("input_data,expected", testdata)
def test_longest_common_subsequence(input_data, expected):
    assert longest_common_subsequence(*input_data) == expected
