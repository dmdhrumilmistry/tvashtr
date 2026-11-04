# qwen3-coder_30b__direct__test vs qwen3-coder_30b__adaptive__test

Problems compared: 82

| | A | B | delta |
|---|---|---|---|
| pass@1 | 92.7% | 93.9% | +1.2% (+1 problems) |
| avg model calls | 1.00 | 3.41 | +2.41 |
| avg output tokens | 186 | 1210 | +1024 |
| avg seconds | 11.3 | 86.2 | +74.9 |

## Improved (1): failed in A, pass in B

- HumanEval/127 `intersection` - A failed with wrong_answer

## Regressed (0): pass in A, failed in B

- none

## Still failing in both (5)

- HumanEval/75 `is_multiply_prime` - A: wrong_answer, B: wrong_answer
- HumanEval/93 `encode` - A: wrong_answer, B: wrong_answer
- HumanEval/115 `max_fill` - A: wrong_answer, B: wrong_answer
- HumanEval/145 `order_by_points` - A: wrong_answer, B: wrong_answer
- HumanEval/163 `generate_integers` - A: wrong_answer, B: wrong_answer

## Failure types

| type | A | B |
|---|---|---|
| wrong_answer | 6 | 5 |
