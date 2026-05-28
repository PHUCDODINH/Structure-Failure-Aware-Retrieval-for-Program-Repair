import re
import ast

PAIR_PATTERN = re.compile(r"Pair\((\d+),\s*(\d+)\)")


def convert_pairs(expr: str):
    """
    Convert Pair(a,b) into ('PAIR', a, b)
    so we can reconstruct actual Pair objects later.
    """
    def repl(match):
        a = int(match.group(1))
        b = int(match.group(2))
        return f"('PAIR', {a}, {b})"

    return PAIR_PATTERN.sub(repl, expr)


def safe_parse_tests(raw_tests):
    """
    Parse MBPP tests like:
    "assert f([Pair(5,6)], 4) == 3"
    into:
    [{"input": [...], "output": ...}]
    """

    parsed = []

    for line in raw_tests:
        line = line.strip()
        if not line.startswith("assert"):
            continue

        try:
            # Remove "assert "
            expr = line[len("assert "):]

            # Split input and expected output
            left, right = expr.split("==")
            expected = ast.literal_eval(convert_pairs(right.strip()))

            # Extract arguments inside the parentheses
            fn_call = left.strip()
            args_str = fn_call[fn_call.index("(")+1 : fn_call.rindex(")")]

            # Convert Pair objects
            args_str = convert_pairs(args_str)

            # args becomes a python list containing tuples ('PAIR', a, b)
            args = ast.literal_eval(f"[{args_str}]")

            parsed.append({"input": args, "output": expected})

        except Exception as e:
            print("[TEST PARSE ERROR]", line)
            print(e)

    return parsed
