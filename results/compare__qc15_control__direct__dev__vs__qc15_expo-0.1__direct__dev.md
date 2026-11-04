# qc15_control__direct__dev vs qc15_expo-0.1__direct__dev

Problems compared: 82

| | A | B | delta |
|---|---|---|---|
| pass@1 | 72.0% | 73.2% | +1.2% (+1 problems) |
| avg model calls | 1.00 | 1.00 | +0.00 |
| avg output tokens | 114 | 122 | +8 |
| avg seconds | 6.9 | 7.3 | +0.4 |

## Improved (2): failed in A, pass in B

- HumanEval/6 `parse_nested_parens` - A failed with wrong_answer
- HumanEval/102 `choose_num` - A failed with wrong_answer

## Regressed (1): pass in A, failed in B

- HumanEval/154 `cycpattern_check` - B fails with wrong_answer

## Still failing in both (21)

- HumanEval/10 `make_palindrome` - A: wrong_answer, B: wrong_answer
- HumanEval/26 `remove_duplicates` - A: wrong_answer, B: wrong_answer
- HumanEval/32 `find_zero` - A: wrong_answer, B: wrong_answer
- HumanEval/54 `same_chars` - A: wrong_answer, B: wrong_answer
- HumanEval/70 `strange_sort_list` - A: wrong_answer, B: wrong_answer
- HumanEval/74 `total_match` - A: wrong_answer, B: wrong_answer
- HumanEval/90 `next_smallest` - A: wrong_answer, B: wrong_answer
- HumanEval/100 `make_a_pile` - A: timeout, B: wrong_answer
- HumanEval/104 `unique_digits` - A: runtime:TypeError, B: runtime:TypeError
- HumanEval/106 `f` - A: wrong_answer, B: runtime:NameError
- HumanEval/108 `count_nums` - A: wrong_answer, B: wrong_answer
- HumanEval/120 `maximum` - A: wrong_answer, B: wrong_answer
- HumanEval/126 `is_sorted` - A: wrong_answer, B: wrong_answer
- HumanEval/128 `prod_signs` - A: wrong_answer, B: wrong_answer
- HumanEval/130 `tri` - A: runtime:IndexError, B: runtime:IndexError
- HumanEval/132 `is_nested` - A: wrong_answer, B: wrong_answer
- HumanEval/134 `check_if_last_char_is_a_letter` - A: wrong_answer, B: wrong_answer
- HumanEval/140 `fix_spaces` - A: wrong_answer, B: wrong_answer
- HumanEval/142 `sum_squares` - A: wrong_answer, B: wrong_answer
- HumanEval/148 `bf` - A: wrong_answer, B: wrong_answer
- HumanEval/160 `do_algebra` - A: wrong_answer, B: wrong_answer

## Failure types

| type | A | B |
|---|---|---|
| runtime:IndexError | 1 | 1 |
| runtime:NameError | 0 | 1 |
| runtime:TypeError | 1 | 1 |
| timeout | 1 | 0 |
| wrong_answer | 20 | 19 |
