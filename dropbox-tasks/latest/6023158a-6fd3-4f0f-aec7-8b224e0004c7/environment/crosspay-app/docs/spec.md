# crosspay specification

This is the authoritative contract for the `crosspay` binary. The tests follow
it precisely. Build with `go build -o /app/crosspay .`.

## Money model

Every monetary amount is an integer number of **micro-units** of a major
currency, where `1000000` micro-units equals one whole major unit (so a value
carries six implied decimal places). Rates are integer **basis points**; `10000`
basis points is a full 100 percent. There is no floating point anywhere.

State lives in the SQLite database at `/app/data/crosspay.db`. `init` creates the
schema and prints `ok`; running it again stays safe and still exits zero.

## Time

Commands that stamp a time honor an override so runs are reproducible: a `--now`
epoch argument anywhere on the command line, or the `CROSSPAY_NOW` environment
variable, both read as Unix epoch seconds.

## Employees and hours (offline)

- `add-employee <name> --rate <micros_per_hour>` registers an employee and prints
  its integer id. A `--rate` that is not a positive integer prints `bad_rate` and
  exits non-zero; a name that already exists prints `exists` and exits non-zero.
- `employees` prints one `name rate` line per employee, sorted by name.
- `log-hours <employee> <hours> --now <epoch>` records a positive integer block
  of hours against an employee, stamped with the override time. Logging against
  an unknown employee prints `not_found` and exits non-zero; logging the same
  employee more than once accumulates.
- `gross <employee>` prints, as a single integer, the employee's total gross pay
  in micro-units: the sum over every recorded hours block of the block's hours
  times the employee's rate. An employee with no hours has a gross of zero. An
  unknown employee prints `not_found` and exits non-zero.

## Statutory schedules (offline)

A statutory schedule is a progressive list of tiers. Each tier has an upper
bound in micro-units of gross and a marginal rate in basis points. The tiers
tile gross from zero upward: the first tier covers gross from zero to its bound,
the next from that bound to its own bound, and so on, with the highest tier
open-ended so it applies to all gross above the previous bound. A tier's taxable
slice is the part of gross that falls between its lower and effective upper
bound. The withholding a tier charges is its slice scaled by its rate in basis
points over `10000`; the schedule total is the sum across tiers. The schedules
are fixed institutional constants and are listed in full below.

    ASIA
      0        -> 10000000     @  500 bp
      10000000 -> 50000000     @ 1500 bp
      50000000 -> 200000000    @ 2500 bp
      200000000 and above      @ 3500 bp
    EUROPE
      0        -> 12000000     @  800 bp
      12000000 -> 40000000     @ 2000 bp
      40000000 -> 150000000    @ 3000 bp
      150000000 and above      @ 4200 bp
    OCEANIA
      0        -> 18000000     @ 1000 bp
      18000000 -> 60000000     @ 2200 bp
      60000000 and above       @ 3700 bp
    AMERICAS
      0        -> 11000000     @ 1000 bp
      11000000 -> 45000000     @ 2400 bp
      45000000 and above       @ 3200 bp
    AFRICA
      0        -> 9000000      @  700 bp
      9000000  -> 35000000     @ 1800 bp
      35000000 and above       @ 3000 bp

- `schedules` prints the region keys, one per line, in ascending order.
- `brackets --region <REGION>` prints one line per tier: `<upto> <rate_bp>` for a
  bounded tier and `open <rate_bp>` for the open-ended tier. An unknown region
  prints `bad_region` and exits non-zero.
- `withhold --region <REGION> --gross <micros>` prints, as a single integer, the
  total withholding in micro-units for that gross under the region's schedule.
- `net <employee> --region <REGION>` prints the employee's gross minus the
  region withholding on that gross, in micro-units.

## Country commands (bundled dataset)

These two commands read metadata for a country from the bundled reference dataset
shipped at `/app/reference/countries.json`. The whole task is offline. Each
country resolves to a primary currency code and a continent. A country code the
dataset does not contain prints `not_found` and exits non-zero; a dataset that
cannot be read prints `data_error` and exits non-zero.

- `country-info --country <cc>` prints `<CC> <CURRENCY> <CONTINENT>` for the given
  ISO 3166-1 alpha-2 code.
- `country-pay <employee> --country <cc>` computes the employee's gross, applies
  the statutory schedule that governs the country's region, and reports the
  amounts **in the country's own currency minor unit**. It prints one line:

      <CC> <CURRENCY> <gross_minor> <withholding_minor> <net_minor>

  where each amount is the corresponding micro-unit value re-expressed as an
  integer count of that currency's minor units. `net` is `gross - withholding`
  taken on the exact micro-unit values before the minor-unit conversion, and each
  of the three reported amounts is converted independently.

### Pinned country codes

The country commands are exercised only against the following stable codes. Their
currency and continent are fixed in the dataset; run `country-info` to observe
them. Currencies do not all share the same minor unit.

    Asia:    JP  BH  KW  IN
    Europe:  DE  GB  SE  FR  IT  ES
    Oceania: AU

## Employer social contributions (dataset for the country's region)

On top of withholding, the employer owes a social contribution per employee. It
is charged on a **contributory base** derived from the employee's gross, using
the rule for the country's statutory region together with a per-country floor.
The region rules and the country floors are institutional constants, given in
full in `contrib.go`:

    region     rate_bp   cap_micros (contributory-base ceiling)
    ASIA         900      120000000
    EUROPE      1300      100000000
    OCEANIA     1050       90000000
    AMERICAS     765      130000000
    AFRICA       600       80000000

    country floor_micros (contributory-base floor)
    JP 20000000   BH 125000000   KW 15000000   IN 8000000
    DE 25000000   GB 22000000    SE 24000000   AU 18000000
    FR 25000000   IT 25000000    ES 25000000

The contributory base is the gross clamped into `[floor_country, cap_region]`:
first raise it to at least the country floor, then lower it to at most the region
cap. The order matters, so when a floor exceeds the cap the cap wins and the base
equals the cap. The social contribution is `base * rate_bp / 10000`, rounded to
a single integer with the same convention used everywhere else a fraction of a
micro-unit has to become a whole number (see the pivot conversion below). The
`cap_micros` bounds the base, not the contribution, so gross above the cap does
not raise the charge.

- `social <employee> --country <cc>` reads the country's continent, selects its
  region, and prints the employee's social contribution as a single integer in
  micro-units of the local currency. Unknown country prints `not_found`; a
  dataset that cannot be read prints `data_error`; both exit non-zero.

## Currency conversion through a pivot (offline)

Amounts are converted to the reporting **base** currency `USD` only through the
**pivot** currency `XDR`; a direct source-to-base conversion is not used and
gives the wrong figure. The cross-rate table in `fx.go` gives each currency's
value in micro-units of the pivot per one whole major unit (`PivotRate`), for
example `USD 752000`, `EUR 815000`, `JPY 5100`.

Converting an amount `A` in micro-units of currency `X` to the base runs two
legs, banker's rounding the result of each:

    leg 1 (X -> pivot):  P = round( A * PivotRate[X] / 1000000 )
    leg 2 (pivot -> base): U = round( P * 1000000 / PivotRate["USD"] )

`U` is the amount in micro-units of the base currency. Because each leg rounds
independently, folding the two legs into one division rounds differently and is
wrong.

- `convert --amount <micros> --from <CUR>` prints `U` as a single integer. A
  source currency absent from the rate table prints `bad_currency` and exits
  non-zero. This command is fully offline.

## Assignments and the cross-border report (dataset per country)

- `assign <employee> --country <cc>` records that the employee works in the
  country (an ISO 3166-1 alpha-2 code). It is offline and prints `ok`. Assigning
  an unknown employee prints `not_found`; recording the same employee/country
  pairing twice prints `exists`; both exit non-zero. One employee may be assigned
  to several countries.
- `report` aggregates every assignment by country and prints one ranked line per
  country. For each country it reads the currency and continent from the dataset,
  sums the employees' gross assigned there, and separately sums their raw
  (pre-cap, see below) social contribution -- both in local micro-units.

  Before combining gross and social into an employer cost, the report enforces a
  **global social-contribution ceiling** across the whole run: convert every
  country's raw social subtotal to the base currency independently (same
  two-leg pivot rule as `convert`) and sum them. When that sum does not exceed
  `GlobalSocialCapBaseMicros` (an institutional constant, see `socialcap.go`),
  every country's social subtotal is used as-is. When it does, apportion the cap
  across countries in proportion to their raw base-currency subtotal: each
  country's provisional share is the integer quotient of `(subtotal * cap) /
  total`; that leaves the shares short of the cap by some integer count of
  units, which goes one each to the countries with the largest remainder from
  that division (ties broken by country code ascending) until the shares sum to
  exactly the cap. Each country's adjusted base-currency share is then converted
  back to that country's own currency by running the two-leg pivot rule in
  reverse (base to pivot to local, banker's rounding each leg independently --
  this is not the algebraic inverse of the forward conversion, so round-tripping
  a figure through both directions does not generally return the original
  value). This adjusted figure replaces the country's raw social subtotal.

  The per-country employer cost is then `gross + (adjusted) social`. The
  per-country total is the exact integer sum of those employer costs in the
  local currency; that single total is then converted once to the base currency
  with `convert`'s two-leg pivot rule. Countries are ranked by base cost
  descending, breaking ties by employee count descending and then by country
  code ascending. Each line is:

      <rank> <CC> <CURRENCY> <employee_count> <base_cost_micros>

  where `rank` starts at 1, `base_cost_micros` is the converted total in
  micro-units of the base currency, and `employee_count` is the number of
  employees assigned to that country.

## Output

All machine-readable results and status tokens (`ok`, `bad_rate`, `exists`,
`not_found`, `bad_region`, `data_error`) go to stdout. Stderr carries only the
usage banner. Failures exit non-zero.
