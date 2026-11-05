# qc7_control__direct__dev vs qc7_expo-0.1__direct__dev

Problems compared: 82

| | A | B | delta |
|---|---|---|---|
| pass@1 | 91.5% | 91.5% | +0.0% (+0 problems) |
| avg model calls | 1.00 | 1.00 | +0.00 |
| avg output tokens | 89 | 87 | -2 |
| avg seconds | 13.1 | 12.7 | -0.4 |

## Improved (0): failed in A, pass in B

- none

## Regressed (0): pass in A, failed in B

- none

## Still failing in both (7)

- HumanEval/10 `make_palindrome` - A: wrong_answer, B: wrong_answer
- HumanEval/26 `remove_duplicates` - A: wrong_answer, B: wrong_answer
- HumanEval/32 `find_zero` - A: wrong_answer, B: wrong_answer
- HumanEval/120 `maximum` - A: wrong_answer, B: wrong_answer
- HumanEval/130 `tri` - A: runtime:IndexError, B: runtime:IndexError
- HumanEval/132 `is_nested` - A: wrong_answer, B: wrong_answer
- HumanEval/142 `sum_squares` - A: wrong_answer, B: wrong_answer

## Failure types

| type | A | B |
|---|---|---|
| runtime:IndexError | 1 | 1 |
| wrong_answer | 6 | 6 |
