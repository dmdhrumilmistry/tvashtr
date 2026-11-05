# qc15_control__direct__dev vs qc15_control__s_star__dev

Problems compared: 82

| | A | B | delta |
|---|---|---|---|
| pass@1 | 72.0% | 85.4% | +13.4% (+11 problems) |
| avg model calls | 1.00 | 8.32 | +7.32 |
| avg output tokens | 114 | 2536 | +2423 |
| avg seconds | 6.9 | 29.5 | +22.6 |

## Improved (13): failed in A, pass in B

- HumanEval/6 `parse_nested_parens` - A failed with wrong_answer
- HumanEval/32 `find_zero` - A failed with wrong_answer
- HumanEval/54 `same_chars` - A failed with wrong_answer
- HumanEval/90 `next_smallest` - A failed with wrong_answer
- HumanEval/100 `make_a_pile` - A failed with timeout
- HumanEval/102 `choose_num` - A failed with wrong_answer
- HumanEval/104 `unique_digits` - A failed with runtime:TypeError
- HumanEval/106 `f` - A failed with wrong_answer
- HumanEval/128 `prod_signs` - A failed with wrong_answer
- HumanEval/134 `check_if_last_char_is_a_letter` - A failed with wrong_answer
- HumanEval/140 `fix_spaces` - A failed with wrong_answer
- HumanEval/142 `sum_squares` - A failed with wrong_answer
- HumanEval/148 `bf` - A failed with wrong_answer

## Regressed (2): pass in A, failed in B

- HumanEval/50 `decode_shift` - B fails with syntax_error
- HumanEval/88 `sort_array` - B fails with wrong_answer

## Still failing in both (10)

- HumanEval/10 `make_palindrome` - A: wrong_answer, B: wrong_answer
- HumanEval/26 `remove_duplicates` - A: wrong_answer, B: wrong_answer
- HumanEval/70 `strange_sort_list` - A: wrong_answer, B: runtime:ValueError
- HumanEval/74 `total_match` - A: wrong_answer, B: wrong_answer
- HumanEval/108 `count_nums` - A: wrong_answer, B: wrong_answer
- HumanEval/120 `maximum` - A: wrong_answer, B: wrong_answer
- HumanEval/126 `is_sorted` - A: wrong_answer, B: wrong_answer
- HumanEval/130 `tri` - A: runtime:IndexError, B: wrong_answer
- HumanEval/132 `is_nested` - A: wrong_answer, B: wrong_answer
- HumanEval/160 `do_algebra` - A: wrong_answer, B: wrong_answer

## Failure types

| type | A | B |
|---|---|---|
| runtime:IndexError | 1 | 0 |
| runtime:TypeError | 1 | 0 |
| runtime:ValueError | 0 | 1 |
| syntax_error | 0 | 1 |
| timeout | 1 | 0 |
| wrong_answer | 20 | 10 |
