# Question and output schema

Compute the number of net checkouts of the adult nonfiction collection during
fiscal year 2024, broken down by branch.

Write the result as JSON to /app/answer.json with exactly these fields:

  answer
    Integer. The total number of adult nonfiction net checkouts across all
    branches during fiscal year 2024.

  by_branch
    Object mapping each branch id to its number of adult nonfiction net checkouts
    during fiscal year 2024. The branch values sum to answer.

  n_events_fy2024
    Integer. The number of distinct circulation events that fall within fiscal
    year 2024, counted across every transaction type and every status. Both OK
    and VOID events are counted here.

  n_renewals_excluded
    Integer. The number of fiscal year 2024 renewal events on adult nonfiction
    items.

  n_adult_nonfiction_items
    Integer. The number of distinct catalog items belonging to the adult
    nonfiction collection.

Example shape (values are illustrative, not the answer):

{
  "answer": 4200,
  "by_branch": {"B01": 1400, "B02": 1300, "B03": 1500},
  "n_events_fy2024": 40000,
  "n_renewals_excluded": 2100,
  "n_adult_nonfiction_items": 1900
}
