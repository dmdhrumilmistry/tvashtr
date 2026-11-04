# qc05_control__direct__dev vs qc05_expo-0.1__direct__dev

Problems compared: 82

| | A | B | delta |
|---|---|---|---|
| pass@1 | 53.7% | 41.5% | -12.2% (-10 problems) |
| avg model calls | 1.00 | 1.00 | +0.00 |
| avg output tokens | 370 | 424 | +54 |
| avg seconds | 9.2 | 19.3 | +10.1 |

## Improved (9): failed in A, pass in B

- HumanEval/20 `find_closest_elements` - A failed with wrong_answer
- HumanEval/64 `vowels_count` - A failed with syntax_error
- HumanEval/68 `pluck` - A failed with runtime:AttributeError
- HumanEval/72 `will_it_fly` - A failed with wrong_answer
- HumanEval/76 `is_simple_power` - A failed with wrong_answer
- HumanEval/88 `sort_array` - A failed with syntax_error
- HumanEval/96 `count_up_to` - A failed with wrong_answer
- HumanEval/102 `choose_num` - A failed with wrong_answer
- HumanEval/156 `int_to_mini_roman` - A failed with runtime:TypeError

## Regressed (19): pass in A, failed in B

- HumanEval/0 `has_close_elements` - B fails with wrong_answer
- HumanEval/4 `mean_absolute_deviation` - B fails with wrong_answer
- HumanEval/24 `largest_divisor` - B fails with wrong_answer
- HumanEval/36 `fizz_buzz` - B fails with wrong_answer
- HumanEval/40 `triples_sum_to_zero` - B fails with wrong_answer
- HumanEval/46 `fib4` - B fails with wrong_answer
- HumanEval/56 `correct_bracketing` - B fails with syntax_error
- HumanEval/82 `prime_length` - B fails with wrong_answer
- HumanEval/84 `solve` - B fails with wrong_answer
- HumanEval/86 `anti_shuffle` - B fails with wrong_answer
- HumanEval/90 `next_smallest` - B fails with wrong_answer
- HumanEval/94 `skjkasdkd` - B fails with wrong_answer
- HumanEval/98 `count_upper` - B fails with wrong_answer
- HumanEval/106 `f` - B fails with wrong_answer
- HumanEval/114 `minSubArraySum` - B fails with wrong_answer
- HumanEval/116 `sort_array` - B fails with wrong_answer
- HumanEval/136 `largest_smallest_integers` - B fails with wrong_answer
- HumanEval/146 `specialFilter` - B fails with wrong_answer
- HumanEval/154 `cycpattern_check` - B fails with wrong_answer

## Still failing in both (29)

- HumanEval/6 `parse_nested_parens` - A: wrong_answer, B: wrong_answer
- HumanEval/8 `sum_product` - A: wrong_answer, B: wrong_answer
- HumanEval/10 `make_palindrome` - A: wrong_answer, B: wrong_answer
- HumanEval/26 `remove_duplicates` - A: wrong_answer, B: wrong_answer
- HumanEval/32 `find_zero` - A: wrong_answer, B: runtime:NameError
- HumanEval/38 `decode_cyclic` - A: wrong_answer, B: wrong_answer
- HumanEval/50 `decode_shift` - A: wrong_answer, B: wrong_answer
- HumanEval/58 `common` - A: wrong_answer, B: wrong_answer
- HumanEval/62 `derivative` - A: wrong_answer, B: wrong_answer
- HumanEval/74 `total_match` - A: wrong_answer, B: wrong_answer
- HumanEval/80 `is_happy` - A: wrong_answer, B: syntax_error
- HumanEval/104 `unique_digits` - A: wrong_answer, B: wrong_answer
- HumanEval/108 `count_nums` - A: wrong_answer, B: wrong_answer
- HumanEval/118 `get_closest_vowel` - A: wrong_answer, B: wrong_answer
- HumanEval/120 `maximum` - A: wrong_answer, B: wrong_answer
- HumanEval/122 `add_elements` - A: wrong_answer, B: wrong_answer
- HumanEval/124 `valid_date` - A: runtime:ValueError, B: runtime:ValueError
- HumanEval/126 `is_sorted` - A: wrong_answer, B: wrong_answer
- HumanEval/128 `prod_signs` - A: wrong_answer, B: wrong_answer
- HumanEval/130 `tri` - A: runtime:IndexError, B: wrong_answer
- HumanEval/132 `is_nested` - A: wrong_answer, B: syntax_error
- HumanEval/134 `check_if_last_char_is_a_letter` - A: wrong_answer, B: wrong_answer
- HumanEval/138 `is_equal_to_sum_even` - A: syntax_error, B: wrong_answer
- HumanEval/140 `fix_spaces` - A: wrong_answer, B: wrong_answer
- HumanEval/142 `sum_squares` - A: wrong_answer, B: wrong_answer
- HumanEval/148 `bf` - A: wrong_answer, B: wrong_answer
- HumanEval/158 `find_max` - A: wrong_answer, B: wrong_answer
- HumanEval/160 `do_algebra` - A: wrong_answer, B: wrong_answer
- HumanEval/162 `string_to_md5` - A: syntax_error, B: wrong_answer

## Failure types

| type | A | B |
|---|---|---|
| runtime:AttributeError | 1 | 0 |
| runtime:IndexError | 1 | 0 |
| runtime:NameError | 0 | 1 |
| runtime:TypeError | 1 | 0 |
| runtime:ValueError | 1 | 1 |
| syntax_error | 4 | 3 |
| wrong_answer | 30 | 43 |
