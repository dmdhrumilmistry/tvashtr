# qc15_control__direct__test vs qc15_control__s_star__test

Problems compared: 82

| | A | B | delta |
|---|---|---|---|
| pass@1 | 70.7% | 80.5% | +9.8% (+8 problems) |
| avg model calls | 1.00 | 8.48 | +7.48 |
| avg output tokens | 124 | 3048 | +2924 |
| avg seconds | 1.5 | 35.7 | +34.3 |

## Improved (12): failed in A, pass in B

- HumanEval/37 `sort_even` - A failed with runtime:IndexError
- HumanEval/67 `fruit_distribution` - A failed with runtime:ValueError
- HumanEval/69 `search` - A failed with wrong_answer
- HumanEval/77 `iscube` - A failed with wrong_answer
- HumanEval/83 `starts_one_ends` - A failed with wrong_answer
- HumanEval/91 `is_bored` - A failed with wrong_answer
- HumanEval/103 `rounded_avg` - A failed with wrong_answer
- HumanEval/111 `histogram` - A failed with runtime:ValueError
- HumanEval/127 `intersection` - A failed with wrong_answer
- HumanEval/139 `special_factorial` - A failed with wrong_answer
- HumanEval/155 `even_odd_count` - A failed with wrong_answer
- HumanEval/157 `right_angle_triangle` - A failed with wrong_answer

## Regressed (4): pass in A, failed in B

- HumanEval/87 `get_row` - B fails with wrong_answer
- HumanEval/109 `move_one_ball` - B fails with wrong_answer
- HumanEval/149 `sorted_list_sum` - B fails with wrong_answer
- HumanEval/151 `double_the_difference` - B fails with wrong_answer

## Still failing in both (12)

- HumanEval/75 `is_multiply_prime` - A: wrong_answer, B: wrong_answer
- HumanEval/93 `encode` - A: wrong_answer, B: wrong_answer
- HumanEval/101 `words_string` - A: wrong_answer, B: wrong_answer
- HumanEval/113 `odd_count` - A: wrong_answer, B: syntax_error
- HumanEval/115 `max_fill` - A: wrong_answer, B: wrong_answer
- HumanEval/119 `match_parens` - A: wrong_answer, B: wrong_answer
- HumanEval/129 `minPath` - A: runtime:UnboundLocalError, B: wrong_answer
- HumanEval/135 `can_arrange` - A: wrong_answer, B: wrong_answer
- HumanEval/137 `compare_one` - A: wrong_answer, B: wrong_answer
- HumanEval/141 `file_name_check` - A: wrong_answer, B: wrong_answer
- HumanEval/145 `order_by_points` - A: wrong_answer, B: wrong_answer
- HumanEval/163 `generate_integers` - A: wrong_answer, B: wrong_answer

## Failure types

| type | A | B |
|---|---|---|
| runtime:IndexError | 1 | 0 |
| runtime:UnboundLocalError | 1 | 0 |
| runtime:ValueError | 2 | 0 |
| syntax_error | 0 | 1 |
| wrong_answer | 20 | 15 |
