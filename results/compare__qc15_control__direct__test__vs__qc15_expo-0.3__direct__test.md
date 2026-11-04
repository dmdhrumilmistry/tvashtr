# qc15_control__direct__test vs qc15_expo-0.3__direct__test

Problems compared: 82

| | A | B | delta |
|---|---|---|---|
| pass@1 | 70.7% | 73.2% | +2.4% (+2 problems) |
| avg model calls | 1.00 | 1.00 | +0.00 |
| avg output tokens | 124 | 147 | +23 |
| avg seconds | 1.5 | 1.7 | +0.3 |

## Improved (5): failed in A, pass in B

- HumanEval/67 `fruit_distribution` - A failed with runtime:ValueError
- HumanEval/69 `search` - A failed with wrong_answer
- HumanEval/75 `is_multiply_prime` - A failed with wrong_answer
- HumanEval/111 `histogram` - A failed with runtime:ValueError
- HumanEval/127 `intersection` - A failed with wrong_answer

## Regressed (3): pass in A, failed in B

- HumanEval/87 `get_row` - B fails with wrong_answer
- HumanEval/125 `split_words` - B fails with wrong_answer
- HumanEval/151 `double_the_difference` - B fails with wrong_answer

## Still failing in both (19)

- HumanEval/37 `sort_even` - A: runtime:IndexError, B: runtime:IndexError
- HumanEval/77 `iscube` - A: wrong_answer, B: wrong_answer
- HumanEval/83 `starts_one_ends` - A: wrong_answer, B: wrong_answer
- HumanEval/91 `is_bored` - A: wrong_answer, B: wrong_answer
- HumanEval/93 `encode` - A: wrong_answer, B: wrong_answer
- HumanEval/101 `words_string` - A: wrong_answer, B: wrong_answer
- HumanEval/103 `rounded_avg` - A: wrong_answer, B: wrong_answer
- HumanEval/113 `odd_count` - A: wrong_answer, B: wrong_answer
- HumanEval/115 `max_fill` - A: wrong_answer, B: runtime:NameError
- HumanEval/119 `match_parens` - A: wrong_answer, B: wrong_answer
- HumanEval/129 `minPath` - A: runtime:UnboundLocalError, B: runtime:UnboundLocalError
- HumanEval/135 `can_arrange` - A: wrong_answer, B: wrong_answer
- HumanEval/137 `compare_one` - A: wrong_answer, B: wrong_answer
- HumanEval/139 `special_factorial` - A: wrong_answer, B: wrong_answer
- HumanEval/141 `file_name_check` - A: wrong_answer, B: wrong_answer
- HumanEval/145 `order_by_points` - A: wrong_answer, B: syntax_error
- HumanEval/155 `even_odd_count` - A: wrong_answer, B: wrong_answer
- HumanEval/157 `right_angle_triangle` - A: wrong_answer, B: wrong_answer
- HumanEval/163 `generate_integers` - A: wrong_answer, B: wrong_answer

## Failure types

| type | A | B |
|---|---|---|
| runtime:IndexError | 1 | 1 |
| runtime:NameError | 0 | 1 |
| runtime:UnboundLocalError | 1 | 1 |
| runtime:ValueError | 2 | 0 |
| syntax_error | 0 | 1 |
| wrong_answer | 20 | 18 |
