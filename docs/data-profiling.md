# Data profiling notes

Source: `data/raw/tech_test_survey_data.csv` (sha256 `d54aff6d...0833fda6`)

First pass over the raw file before writing any pipeline code. The aim was to understand the
structure and find anything that would make naive analysis wrong.

## Shape

- 1,499 data rows, 41 columns, UTF-8, CRLF line endings
- Values containing commas are quoted (income bands, some answer options), so the file needs a
  real CSV parser rather than splitting on commas
- Column names are the full question text, up to ~120 characters

## Column groups

| Group | Columns | Type |
|---|---|---|
| ID | `serial_number` | integer, 13 to 1867 (not contiguous) |
| Demographics | gender, age band, actual age, working status, region, household income, employer type, public sector area | single choice, plus age as an integer |
| Politics | political interest, EU referendum vote, voting intention | single choice |
| "Which statements apply to you" | 17 columns | one Yes/No column per statement (multi-select) |
| General attitudes | 11 columns | 5-point agree/disagree scale + Don't know |
| Priorities | most important goal | single choice, 18 options |

There is no weighting variable and no interview date.

## Issues found

| # | Issue | Evidence | Decision |
|---|---|---|---|
| 1 | Duplicate rows | `serial_number` 200 appears 32 times (file lines 150-181), all identical. Unique respondents: **1,468** | Drop exact duplicates. Fail the pipeline if an ID is duplicated with different answers, since that can't be resolved automatically |
| 2 | Broken `£` symbol | Income bands read `ú14,001 to ú21,000` (2,626 occurrences, income column only). The `£` byte (0xA3) has been decoded as code page 850, where 0xA3 is `ú` | Replace `ú` with `£` in the income column and check no `ú` remains anywhere |
| 3 | Routed question | `do_you_work_in` is blank for 1,123 rows. It is only answered by "Other public sector employer" and "Nationalised industry" respondents (376), and is blank for everyone else | Blank means "not asked". Keep as null and use the 376 public sector respondents as the base |
| 4 | EU referendum blanks | 362 blanks. 50% of 18-24s are blank (including all 18 year olds) against 8% of 65+. There is no "did not vote" option | Recode to "Did not vote / not stated" rather than dropping, otherwise the sample skews older |
| 5 | Gaps in property question | `own_more_than_one_property` is 61% blank, while the other statements in the same block have no blanks. Serials 600-999 are 100% blank | Looks like a collection problem in part of fieldwork, not a respondent choice. Keep as null (missing) and flag in the UI |
| 6 | Constant column | `..._dont_know` is "No" for every row | Drop |
| 7 | Ordered categories | Age bands, income bands, political interest and the agree/disagree scale have a natural order. Alphabetical sorting puts "Up to £7,000" last | Store option order in a codebook and use it everywhere |
| 8 | Small subgroups | Some income bands have 9-15 respondents. Gender "Prefer not to say" has 1 | Show base sizes next to every percentage and flag bases under 50 |

## Checks that passed

- Every row parses to 41 fields
- Age band agrees with actual age for every respondent; ages are 18-93
- SNP voters all live in Scotland, Plaid Cymru voters all live in Wales
- Nobody who ticked "None of these" also ticked a statement
- No leading or trailing whitespace in any value
- The only non-ASCII character in the file is the `ú` from issue 2

## Minor inconsistencies (left as-is)

- 2 respondents say they have never worked but are currently working full or part time
- 2 respondents under 50 describe themselves as retired

Too few to change any result, and there is no safe way to correct them. Logged as warnings.
