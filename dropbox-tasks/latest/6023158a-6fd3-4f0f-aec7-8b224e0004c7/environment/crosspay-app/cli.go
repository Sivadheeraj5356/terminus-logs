package main

import (
	"errors"
	"fmt"
	"os"
	"sort"
	"strconv"
	"strings"
)

// splitFlags parses "--name value" pairs out of args, returning the flag map and
// the remaining positionals. An unknown flag or a flag missing its value errors.
func splitFlags(args []string, valueFlags map[string]bool) (map[string]string, []string, error) {
	flags := map[string]string{}
	pos := []string{}
	i := 0
	for i < len(args) {
		a := args[i]
		if len(a) > 2 && a[:2] == "--" {
			if !valueFlags[a] {
				return nil, nil, fmt.Errorf("unknown flag: %s", a)
			}
			if i+1 >= len(args) {
				return nil, nil, fmt.Errorf("%s requires a value", a)
			}
			flags[a] = args[i+1]
			i += 2
			continue
		}
		pos = append(pos, a)
		i++
	}
	return flags, pos, nil
}

// requireEmployee looks up the employee, printing not_found and exiting when the
// employee does not exist.
func requireEmployee(name string) *Employee {
	emp, err := LookupEmployee(name)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if emp == nil {
		fmt.Println("not_found")
		os.Exit(1)
	}
	return emp
}

// pow10 returns 10 raised to n for small non-negative n.
func pow10(n int) int64 {
	r := int64(1)
	for i := 0; i < n; i++ {
		r *= 10
	}
	return r
}

// RoundToMinor rounds a micro-unit amount (six implied decimals) to a currency
// that carries digits minor-unit decimals, returning the integer count of minor
// units. It shares the same rounding convention as the rest of the payroll math
// (see docs/spec.md).
func RoundToMinor(micros int64, digits int) int64 {
	return RoundExact(micros, pow10(6-digits))
}

// CmdInit handles `crosspay init`.
func CmdInit() {
	if err := InitDB(); err != nil {
		fmt.Fprintf(os.Stderr, "init error: %v\n", err)
		os.Exit(1)
	}
	fmt.Println("ok")
}

// CmdAddEmployee handles `crosspay add-employee <name> --rate <micros_per_hour>`.
func CmdAddEmployee(args []string) {
	flags, pos, err := splitFlags(args, map[string]bool{"--rate": true})
	if err != nil || len(pos) < 1 {
		fmt.Fprintln(os.Stderr, "usage: crosspay add-employee <name> --rate <micros_per_hour>")
		os.Exit(1)
	}
	rateStr, ok := flags["--rate"]
	if !ok {
		fmt.Fprintln(os.Stderr, "--rate is required")
		os.Exit(1)
	}
	rate, perr := strconv.ParseInt(rateStr, 10, 64)
	if perr != nil || rate <= 0 {
		fmt.Println("bad_rate")
		os.Exit(1)
	}
	id, err := AddEmployee(pos[0], rate)
	if err != nil {
		if err.Error() == "exists" {
			fmt.Println("exists")
			os.Exit(1)
		}
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Println(id)
}

// CmdEmployees handles `crosspay employees`.
func CmdEmployees(args []string) {
	_ = args
	emps, err := ListEmployees()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	for _, e := range emps {
		fmt.Printf("%s %d\n", e.Name, e.Rate)
	}
}

// CmdLogHours handles `crosspay log-hours <employee> <hours> --now <epoch>`.
func CmdLogHours(args []string) {
	_, pos, err := splitFlags(args, map[string]bool{})
	if err != nil || len(pos) < 2 {
		fmt.Fprintln(os.Stderr, "usage: crosspay log-hours <employee> <hours> --now <epoch>")
		os.Exit(1)
	}
	hours, perr := strconv.ParseInt(pos[1], 10, 64)
	if perr != nil || hours <= 0 {
		fmt.Fprintln(os.Stderr, "invalid hours")
		os.Exit(1)
	}
	emp := requireEmployee(pos[0])
	if err := LogHours(emp, hours, NowUnix()); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

// CmdGross handles `crosspay gross <employee>`.
func CmdGross(args []string) {
	_, pos, err := splitFlags(args, map[string]bool{})
	if err != nil || len(pos) < 1 {
		fmt.Fprintln(os.Stderr, "usage: crosspay gross <employee>")
		os.Exit(1)
	}
	emp := requireEmployee(pos[0])
	g, err := GrossPay(emp)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Println(g)
}

// CmdSchedules handles `crosspay schedules`.
func CmdSchedules(args []string) {
	_ = args
	for _, r := range RegionKeys() {
		fmt.Println(r)
	}
}

// requireSchedule returns the schedule for a region key, exiting with
// bad_region when it is unknown.
func requireSchedule(region string) []Bracket {
	sched, ok := Schedules[region]
	if !ok {
		fmt.Println("bad_region")
		os.Exit(1)
	}
	return sched
}

// CmdBrackets handles `crosspay brackets --region <REGION>`.
func CmdBrackets(args []string) {
	flags, _, err := splitFlags(args, map[string]bool{"--region": true})
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	region, ok := flags["--region"]
	if !ok {
		fmt.Fprintln(os.Stderr, "--region is required")
		os.Exit(1)
	}
	sched := requireSchedule(region)
	for i, b := range sched {
		if i == len(sched)-1 {
			fmt.Printf("open %d\n", b.RateBp)
		} else {
			fmt.Printf("%d %d\n", b.Upto, b.RateBp)
		}
	}
}

// CmdWithhold handles `crosspay withhold --region <REGION> --gross <micros>`.
func CmdWithhold(args []string) {
	flags, _, err := splitFlags(args, map[string]bool{"--region": true, "--gross": true})
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	region, okR := flags["--region"]
	grossStr, okG := flags["--gross"]
	if !okR || !okG {
		fmt.Fprintln(os.Stderr, "usage: crosspay withhold --region <REGION> --gross <micros>")
		os.Exit(1)
	}
	requireSchedule(region)
	gross, perr := strconv.ParseInt(grossStr, 10, 64)
	if perr != nil {
		fmt.Fprintln(os.Stderr, "invalid gross")
		os.Exit(1)
	}
	w, err := WithholdRegion(gross, region)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Println(w)
}

// CmdNet handles `crosspay net <employee> --region <REGION>`.
func CmdNet(args []string) {
	flags, pos, err := splitFlags(args, map[string]bool{"--region": true})
	if err != nil || len(pos) < 1 {
		fmt.Fprintln(os.Stderr, "usage: crosspay net <employee> --region <REGION>")
		os.Exit(1)
	}
	region, ok := flags["--region"]
	if !ok {
		fmt.Fprintln(os.Stderr, "--region is required")
		os.Exit(1)
	}
	requireSchedule(region)
	emp := requireEmployee(pos[0])
	gross, err := GrossPay(emp)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	wh, err := WithholdRegion(gross, region)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Println(gross - wh)
}

// dataFail maps a dataset lookup error onto the right stdout token and exit
// code.
func dataFail(err error) {
	if errors.Is(err, ErrCountryNotFound) {
		fmt.Println("not_found")
		os.Exit(1)
	}
	fmt.Println("data_error")
	os.Exit(1)
}

// CmdCountryInfo handles `crosspay country-info --country <cc>`.
func CmdCountryInfo(args []string) {
	flags, _, err := splitFlags(args, map[string]bool{"--country": true})
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	code, ok := flags["--country"]
	if !ok {
		fmt.Fprintln(os.Stderr, "--country is required")
		os.Exit(1)
	}
	c, err := LoadCountry(code)
	if err != nil {
		dataFail(err)
	}
	fmt.Printf("%s %s %s\n", c.Code, c.Currency, c.Continent)
}

// CmdCountryPay handles `crosspay country-pay <employee> --country <cc>`.
func CmdCountryPay(args []string) {
	flags, pos, err := splitFlags(args, map[string]bool{"--country": true})
	if err != nil || len(pos) < 1 {
		fmt.Fprintln(os.Stderr, "usage: crosspay country-pay <employee> --country <cc>")
		os.Exit(1)
	}
	code, ok := flags["--country"]
	if !ok {
		fmt.Fprintln(os.Stderr, "--country is required")
		os.Exit(1)
	}
	emp := requireEmployee(pos[0])
	c, ferr := LoadCountry(code)
	if ferr != nil {
		dataFail(ferr)
	}
	region, ok := ContinentToRegion(c.Continent)
	if !ok {
		fmt.Println("bad_region")
		os.Exit(1)
	}
	gross, err := GrossPay(emp)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	wh, err := WithholdRegion(gross, region)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	net := gross - wh
	digits := MinorDigits(c.Currency)
	fmt.Printf("%s %s %d %d %d\n",
		c.Code, c.Currency,
		RoundToMinor(gross, digits),
		RoundToMinor(wh, digits),
		RoundToMinor(net, digits),
	)
}

// CmdAssign handles `crosspay assign <employee> --country <cc>`. It records the
// employee/country pairing offline; the country is resolved live only later by
// report. A duplicate pairing prints exists and exits non-zero.
func CmdAssign(args []string) {
	flags, pos, err := splitFlags(args, map[string]bool{"--country": true})
	if err != nil || len(pos) < 1 {
		fmt.Fprintln(os.Stderr, "usage: crosspay assign <employee> --country <cc>")
		os.Exit(1)
	}
	code, ok := flags["--country"]
	if !ok {
		fmt.Fprintln(os.Stderr, "--country is required")
		os.Exit(1)
	}
	emp := requireEmployee(pos[0])
	if err := AddAssignment(emp.ID, strings.ToUpper(strings.TrimSpace(code))); err != nil {
		if err.Error() == "exists" {
			fmt.Println("exists")
			os.Exit(1)
		}
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Println("ok")
}

// CmdSocial handles `crosspay social <employee> --country <cc>`. It fetches the
// country's continent live, selects the statutory region, and prints the
// employer social contribution in integer micro-units of the local currency.
func CmdSocial(args []string) {
	flags, pos, err := splitFlags(args, map[string]bool{"--country": true})
	if err != nil || len(pos) < 1 {
		fmt.Fprintln(os.Stderr, "usage: crosspay social <employee> --country <cc>")
		os.Exit(1)
	}
	code, ok := flags["--country"]
	if !ok {
		fmt.Fprintln(os.Stderr, "--country is required")
		os.Exit(1)
	}
	emp := requireEmployee(pos[0])
	c, ferr := LoadCountry(code)
	if ferr != nil {
		dataFail(ferr)
	}
	region, ok := ContinentToRegion(c.Continent)
	if !ok {
		fmt.Println("bad_region")
		os.Exit(1)
	}
	gross, err := GrossPay(emp)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	s, err := SocialContribution(gross, region, c.Code)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Println(s)
}

// CmdConvert handles `crosspay convert --amount <micros> --from <CUR>`. It is
// offline: it converts the amount to the reporting base currency through the
// pivot and prints the result in integer micro-units of the base.
func CmdConvert(args []string) {
	flags, _, err := splitFlags(args, map[string]bool{"--amount": true, "--from": true})
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	amtStr, okA := flags["--amount"]
	cur, okC := flags["--from"]
	if !okA || !okC {
		fmt.Fprintln(os.Stderr, "usage: crosspay convert --amount <micros> --from <CUR>")
		os.Exit(1)
	}
	amount, perr := strconv.ParseInt(amtStr, 10, 64)
	if perr != nil {
		fmt.Fprintln(os.Stderr, "invalid amount")
		os.Exit(1)
	}
	base, err := ConvertToBase(amount, strings.ToUpper(strings.TrimSpace(cur)))
	if err != nil {
		fmt.Println("bad_currency")
		os.Exit(1)
	}
	fmt.Println(base)
}

// CmdReport handles `crosspay report`. It aggregates every assignment by
// country, fetches each country's currency and continent live, computes each
// country's gross subtotal and raw (pre-cap) social-contribution subtotal in the
// local currency, enforces the global social-contribution ceiling across every
// country via ApplyGlobalSocialCap, then sums the employer cost (gross plus the
// possibly-adjusted social contribution) in the local currency, converts the
// per-country total once to the base currency, ranks the countries, and prints
// one ranked line each.
func CmdReport(args []string) {
	_ = args
	assigns, err := ListAssignments()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	byCountry := map[string][]Assignment{}
	order := []string{}
	for _, a := range assigns {
		if _, seen := byCountry[a.Country]; !seen {
			order = append(order, a.Country)
		}
		byCountry[a.Country] = append(byCountry[a.Country], a)
	}
	sort.Strings(order)

	type countryPrep struct {
		Code, Currency string
		Count          int
		Gross          int64
		RawSocial      int64
	}
	preps := []countryPrep{}
	for _, cc := range order {
		c, ferr := LoadCountry(cc)
		if ferr != nil {
			dataFail(ferr)
		}
		region, ok := ContinentToRegion(c.Continent)
		if !ok {
			fmt.Println("bad_region")
			os.Exit(1)
		}
		var gross, rawSocial int64
		for _, a := range byCountry[cc] {
			emp := &Employee{ID: a.EmployeeID, Name: a.EmployeeName, Rate: a.Rate}
			g, gerr := GrossPay(emp)
			if gerr != nil {
				fmt.Fprintln(os.Stderr, gerr)
				os.Exit(1)
			}
			s, serr := SocialContribution(g, region, c.Code)
			if serr != nil {
				fmt.Fprintln(os.Stderr, serr)
				os.Exit(1)
			}
			gross += g
			rawSocial += s
		}
		preps = append(preps, countryPrep{
			Code: c.Code, Currency: c.Currency, Count: len(byCountry[cc]),
			Gross: gross, RawSocial: rawSocial,
		})
	}

	subtotals := make([]CountrySocialSubtotal, len(preps))
	for i, p := range preps {
		subtotals[i] = CountrySocialSubtotal{Code: p.Code, Currency: p.Currency, Local: p.RawSocial}
	}
	adjustedSocial := ApplyGlobalSocialCap(subtotals)

	rows := []CountryAgg{}
	for _, p := range preps {
		local := p.Gross + adjustedSocial[p.Code]
		baseCost, cerr := ConvertToBase(local, p.Currency)
		if cerr != nil {
			fmt.Println("bad_currency")
			os.Exit(1)
		}
		rows = append(rows, CountryAgg{
			Code:      p.Code,
			Currency:  p.Currency,
			Count:     p.Count,
			LocalCost: local,
			BaseCost:  baseCost,
		})
	}

	for i, r := range RankCountries(rows) {
		fmt.Printf("%d %s %s %d %d\n", i+1, r.Code, r.Currency, r.Count, r.BaseCost)
	}
}
