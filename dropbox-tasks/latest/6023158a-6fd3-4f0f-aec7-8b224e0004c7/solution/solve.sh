#!/usr/bin/env bash
set -euo pipefail

# Reference solution for restcountries-payroll (crosspay). Fills in the stubbed
# employee/hours storage, the progressive half-even withholding math, the ISO
# 4217 minor-unit mapping, and the continent-to-region mapping, then builds the
# binary at /app/crosspay.

APP_DIR="/app"

# --- employees.go (SQLite-backed employee store) ----------------------------
cat > "$APP_DIR/employees.go" << 'GOEOF'
package main

import (
	"fmt"
	"strconv"
	"strings"
)

// LookupEmployee returns the employee with the given name, or nil when unknown.
func LookupEmployee(name string) (*Employee, error) {
	rows, err := sqliteQuery(fmt.Sprintf(
		"SELECT id, name, rate FROM employees WHERE name = %s LIMIT 1;", sqlQuote(name),
	))
	if err != nil {
		return nil, err
	}
	if len(rows) == 0 || strings.TrimSpace(rows[0]) == "" {
		return nil, nil
	}
	parts := strings.SplitN(rows[0], "|", 3)
	if len(parts) < 3 {
		return nil, nil
	}
	id, _ := strconv.ParseInt(strings.TrimSpace(parts[0]), 10, 64)
	rate, _ := strconv.ParseInt(strings.TrimSpace(parts[2]), 10, 64)
	return &Employee{ID: id, Name: parts[1], Rate: rate}, nil
}

// AddEmployee creates a new employee and returns its id. Returns "exists" when
// the name is already registered.
func AddEmployee(name string, rate int64) (int64, error) {
	rows, err := sqliteQuery(fmt.Sprintf(
		"SELECT 1 FROM employees WHERE name = %s LIMIT 1;", sqlQuote(name),
	))
	if err != nil {
		return 0, err
	}
	if len(rows) > 0 && strings.TrimSpace(rows[0]) != "" {
		return 0, fmt.Errorf("exists")
	}
	out, err := sqliteExec(fmt.Sprintf(
		"INSERT INTO employees (name, rate) VALUES (%s, %d); SELECT last_insert_rowid();",
		sqlQuote(name), rate,
	))
	if err != nil {
		return 0, err
	}
	id, _ := strconv.ParseInt(strings.TrimSpace(out), 10, 64)
	return id, nil
}

// ListEmployees returns every employee sorted by name.
func ListEmployees() ([]Employee, error) {
	rows, err := sqliteQuery("SELECT id, name, rate FROM employees ORDER BY name;")
	if err != nil {
		return nil, err
	}
	out := []Employee{}
	for _, r := range rows {
		if strings.TrimSpace(r) == "" {
			continue
		}
		parts := strings.SplitN(r, "|", 3)
		if len(parts) < 3 {
			continue
		}
		id, _ := strconv.ParseInt(strings.TrimSpace(parts[0]), 10, 64)
		rate, _ := strconv.ParseInt(strings.TrimSpace(parts[2]), 10, 64)
		out = append(out, Employee{ID: id, Name: parts[1], Rate: rate})
	}
	return out, nil
}
GOEOF

# --- hours.go (hours log + gross) -------------------------------------------
cat > "$APP_DIR/hours.go" << 'GOEOF'
package main

import (
	"fmt"
	"strconv"
	"strings"
)

// LogHours records a block of hours worked by the employee at time ts.
func LogHours(emp *Employee, hours, ts int64) error {
	_, err := sqliteExec(fmt.Sprintf(
		"INSERT INTO hours (employee_id, hours, ts) VALUES (%d, %d, %d);",
		emp.ID, hours, ts,
	))
	return err
}

// GrossPay returns the total gross pay in integer micro-units for the employee:
// the sum of every recorded block's hours, times the employee's rate.
func GrossPay(emp *Employee) (int64, error) {
	rows, err := sqliteQuery(fmt.Sprintf(
		"SELECT COALESCE(SUM(hours),0) FROM hours WHERE employee_id = %d;", emp.ID,
	))
	if err != nil {
		return 0, err
	}
	var total int64
	if len(rows) > 0 {
		total, _ = strconv.ParseInt(strings.TrimSpace(rows[0]), 10, 64)
	}
	return total * emp.Rate, nil
}
GOEOF

# --- withhold.go (half-even progressive withholding) ------------------------
cat > "$APP_DIR/withhold.go" << 'GOEOF'
package main

import "fmt"

// RoundExact returns num/den rounded half-to-even using exact integer math.
// For non-negative num and positive den it takes the integer quotient and
// remainder, rounds down when twice the remainder is below den, up when above,
// and on an exact tie rounds to the nearest even quotient.
func RoundExact(num, den int64) int64 {
	if den == 0 {
		return 0
	}
	q := num / den
	r := num % den
	twice := r * 2
	if twice < den {
		return q
	}
	if twice > den {
		return q + 1
	}
	if q%2 == 0 {
		return q
	}
	return q + 1
}

// WithholdRegion returns the total marginal withholding in integer micro-units
// for the given gross under the named region's statutory schedule. Each tier
// charges its rate on the slice of gross between its lower and effective upper
// bound; the highest tier is open-ended. Every per-tier amount is banker's
// rounded.
func WithholdRegion(gross int64, region string) (int64, error) {
	sched, ok := Schedules[region]
	if !ok {
		return 0, fmt.Errorf("bad_region")
	}
	var total, lower int64
	for i, b := range sched {
		upper := b.Upto
		if i == len(sched)-1 {
			upper = gross // open-ended top tier
		}
		if upper > gross {
			upper = gross
		}
		slice := upper - lower
		if slice < 0 {
			slice = 0
		}
		total += RoundExact(slice*b.RateBp, 10000)
		lower = b.Upto
	}
	return total, nil
}
GOEOF

# --- currency.go (ISO 4217 minor units) -------------------------------------
cat > "$APP_DIR/currency.go" << 'GOEOF'
package main

import "strings"

// MinorDigits returns the number of minor-unit decimal places a currency carries
// per ISO 4217. Most currencies use two; a handful use zero (no minor unit) and
// a handful use three.
func MinorDigits(currency string) int {
	switch strings.ToUpper(strings.TrimSpace(currency)) {
	case "JPY", "KRW", "CLP", "ISK", "VND", "XOF", "XAF", "PYG", "RWF", "UGX", "VUV":
		return 0
	case "BHD", "KWD", "OMR", "JOD", "TND", "IQD", "LYD":
		return 3
	default:
		return 2
	}
}
GOEOF

# --- mapping.go (continent -> statutory region) -----------------------------
cat > "$APP_DIR/mapping.go" << 'GOEOF'
package main

import "strings"

// ContinentToRegion maps a continent name from the live country API onto a
// statutory schedule region key. North and South America share one schedule.
func ContinentToRegion(continent string) (string, bool) {
	switch strings.ToUpper(strings.TrimSpace(continent)) {
	case "ASIA":
		return "ASIA", true
	case "EUROPE":
		return "EUROPE", true
	case "OCEANIA":
		return "OCEANIA", true
	case "NORTH AMERICA", "SOUTH AMERICA", "AMERICAS":
		return "AMERICAS", true
	case "AFRICA":
		return "AFRICA", true
	default:
		return "", false
	}
}
GOEOF

# --- social.go (region-tiered social contribution, floor then cap) ----------
cat > "$APP_DIR/social.go" << 'GOEOF'
package main

import "fmt"

// SocialContribution returns the employer social contribution in integer
// micro-units. The contributory base starts from gross, is raised to at least
// the country floor, then clamped down to at most the region cap (so the cap
// wins when a floor exceeds it). The contribution is that base times the region
// rate in basis points over 10000, banker's rounded.
func SocialContribution(gross int64, region, country string) (int64, error) {
	rule, ok := SocialParams[region]
	if !ok {
		return 0, fmt.Errorf("bad_region")
	}
	base := gross
	if floor, ok := CountryFloor[country]; ok && floor > base {
		base = floor
	}
	if base > rule.CapMicros {
		base = rule.CapMicros
	}
	return RoundExact(base*rule.RateBp, 10000), nil
}
GOEOF

# --- convert.go (local -> pivot -> base, half-even each leg) -----------------
cat > "$APP_DIR/convert.go" << 'GOEOF'
package main

import "fmt"

// ConvertToBase converts amount micro-units of `from` into micro-units of the
// base currency in two legs, banker's rounding each leg: first to the pivot
// currency (amount * rate[from] / 1000000), then from the pivot to the base
// (pivot * 1000000 / rate[base]). Converting straight through with a single
// rounding gives a different, wrong answer.
func ConvertToBase(amount int64, from string) (int64, error) {
	rFrom, ok := PivotRate[from]
	if !ok {
		return 0, fmt.Errorf("bad_currency")
	}
	rBase, ok := PivotRate[BaseCurrency]
	if !ok {
		return 0, fmt.Errorf("bad_currency")
	}
	pivot := RoundExact(amount*rFrom, 1000000)
	return RoundExact(pivot*1000000, rBase), nil
}

// convertFromBase converts amount micro-units of the base currency into
// micro-units of `to`, mirroring ConvertToBase's two legs in reverse: first
// base to pivot, then pivot to the target, banker's rounding each leg
// independently. This is not the algebraic inverse of ConvertToBase -- each
// leg still rounds on its own -- so round-tripping an amount through
// ConvertToBase and back does not generally reproduce the original figure.
func convertFromBase(amount int64, to string) (int64, error) {
	rTo, ok := PivotRate[to]
	if !ok {
		return 0, fmt.Errorf("bad_currency")
	}
	rBase, ok := PivotRate[BaseCurrency]
	if !ok {
		return 0, fmt.Errorf("bad_currency")
	}
	pivot := RoundExact(amount*rBase, 1000000)
	return RoundExact(pivot*1000000, rTo), nil
}
GOEOF

# --- socialcap.go (global social-contribution ceiling, largest-remainder) ---
cat > "$APP_DIR/socialcap.go" << 'GOEOF'
package main

import "sort"

// GlobalSocialCapBaseMicros is the fixed ceiling, in micro-units of the base
// currency, on the sum of every country's raw employer social-contribution
// subtotal for a report run, once each country's subtotal is independently
// converted to the base currency.
const GlobalSocialCapBaseMicros int64 = 100000000

// CountrySocialSubtotal is one country's raw, pre-cap employer
// social-contribution subtotal, in micro-units of its own currency.
type CountrySocialSubtotal struct {
	Code     string
	Currency string
	Local    int64
}

// ApplyGlobalSocialCap enforces GlobalSocialCapBaseMicros across a report run.
// It converts each country's raw subtotal to the base currency and sums them;
// when the sum does not exceed the cap every subtotal passes through unchanged.
// Otherwise it apportions the cap across countries proportional to their raw
// base-currency subtotal using largest-remainder allocation (integer quotient
// as the provisional share, the countries with the largest remainder from that
// division get one extra unit each, ties broken by country code ascending,
// until the shares sum exactly to the cap), then converts each country's
// adjusted base-currency share back to its own currency.
func ApplyGlobalSocialCap(subtotals []CountrySocialSubtotal) map[string]int64 {
	rawBase := map[string]int64{}
	var total int64
	for _, s := range subtotals {
		b, err := ConvertToBase(s.Local, s.Currency)
		if err != nil {
			b = 0
		}
		rawBase[s.Code] = b
		total += b
	}

	out := map[string]int64{}
	if total <= GlobalSocialCapBaseMicros || total == 0 {
		for _, s := range subtotals {
			out[s.Code] = s.Local
		}
		return out
	}

	type share struct {
		code      string
		floor     int64
		remainder int64
	}
	shares := make([]share, len(subtotals))
	var sumFloors int64
	for i, s := range subtotals {
		num := rawBase[s.Code] * GlobalSocialCapBaseMicros
		q := num / total
		r := num % total
		shares[i] = share{code: s.Code, floor: q, remainder: r}
		sumFloors += q
	}
	deficit := GlobalSocialCapBaseMicros - sumFloors

	ranked := make([]share, len(shares))
	copy(ranked, shares)
	sort.Slice(ranked, func(i, j int) bool {
		if ranked[i].remainder != ranked[j].remainder {
			return ranked[i].remainder > ranked[j].remainder
		}
		return ranked[i].code < ranked[j].code
	})

	adjustedBase := map[string]int64{}
	for _, sh := range shares {
		adjustedBase[sh.code] = sh.floor
	}
	for i := int64(0); i < deficit; i++ {
		adjustedBase[ranked[i].code]++
	}

	for _, s := range subtotals {
		local, err := convertFromBase(adjustedBase[s.Code], s.Currency)
		if err != nil {
			local = 0
		}
		out[s.Code] = local
	}
	return out
}
GOEOF

# --- assignments.go (SQLite-backed employee/country pairings) ----------------
cat > "$APP_DIR/assignments.go" << 'GOEOF'
package main

import (
	"fmt"
	"strconv"
	"strings"
)

// Assignment is one employee placed to work in one country.
type Assignment struct {
	EmployeeID   int64
	EmployeeName string
	Rate         int64
	Country      string
}

// AddAssignment records an employee/country pairing, returning "exists" when it
// is already recorded.
func AddAssignment(empID int64, country string) error {
	rows, err := sqliteQuery(fmt.Sprintf(
		"SELECT 1 FROM assignments WHERE employee_id = %d AND country = %s LIMIT 1;",
		empID, sqlQuote(country),
	))
	if err != nil {
		return err
	}
	if len(rows) > 0 && strings.TrimSpace(rows[0]) != "" {
		return fmt.Errorf("exists")
	}
	_, err = sqliteExec(fmt.Sprintf(
		"INSERT INTO assignments (employee_id, country) VALUES (%d, %s);",
		empID, sqlQuote(country),
	))
	return err
}

// ListAssignments returns every assignment joined to its employee, ordered by
// country then employee name.
func ListAssignments() ([]Assignment, error) {
	rows, err := sqliteQuery(
		"SELECT a.employee_id, e.name, e.rate, a.country FROM assignments a " +
			"JOIN employees e ON e.id = a.employee_id ORDER BY a.country, e.name;",
	)
	if err != nil {
		return nil, err
	}
	out := []Assignment{}
	for _, r := range rows {
		if strings.TrimSpace(r) == "" {
			continue
		}
		parts := strings.SplitN(r, "|", 4)
		if len(parts) < 4 {
			continue
		}
		id, _ := strconv.ParseInt(strings.TrimSpace(parts[0]), 10, 64)
		rate, _ := strconv.ParseInt(strings.TrimSpace(parts[2]), 10, 64)
		out = append(out, Assignment{
			EmployeeID:   id,
			EmployeeName: parts[1],
			Rate:         rate,
			Country:      strings.TrimSpace(parts[3]),
		})
	}
	return out, nil
}
GOEOF

# --- rank.go (multi-key ordering) -------------------------------------------
cat > "$APP_DIR/rank.go" << 'GOEOF'
package main

import "sort"

// CountryAgg is one country's aggregated cost line for the report.
type CountryAgg struct {
	Code      string
	Currency  string
	Count     int
	LocalCost int64
	BaseCost  int64
}

// RankCountries orders rows by BaseCost descending, then Count descending, then
// Code ascending.
func RankCountries(rows []CountryAgg) []CountryAgg {
	out := make([]CountryAgg, len(rows))
	copy(out, rows)
	sort.SliceStable(out, func(i, j int) bool {
		a, b := out[i], out[j]
		if a.BaseCost != b.BaseCost {
			return a.BaseCost > b.BaseCost
		}
		if a.Count != b.Count {
			return a.Count > b.Count
		}
		return a.Code < b.Code
	})
	return out
}
GOEOF

cd "$APP_DIR"
go build -o /app/crosspay .
echo "Build successful: /app/crosspay"
