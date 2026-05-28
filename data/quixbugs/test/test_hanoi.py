import pytest
from load_testdata import load_json_testcases

if pytest.use_correct:
    from data.quixbugs.correct.hanoi import hanoi
else:
    from data.quixbugs.buggy.hanoi import hanoi


testdata = load_json_testcases(hanoi.__name__)
testdata = [[inp, [tuple(x) for x in out]] for inp, out in testdata]


@pytest.mark.parametrize("input_data,expected", testdata)
def test_hanoi(input_data, expected):
    assert hanoi(*input_data) == expected
