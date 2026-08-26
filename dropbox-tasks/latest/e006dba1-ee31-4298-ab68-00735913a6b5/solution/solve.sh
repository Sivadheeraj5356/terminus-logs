#!/bin/bash
set -euo pipefail

# waterfall engine -- sequential/pro-rata with PIK and cleanup
cat > /app/waterfall.go << 'EOF'
package main

import (
	"encoding/json"
	"math"
	"os"
)

type Tranche struct {
	ID         string  `json:"id"`
	Class      string  `json:"class"`
	Balance    float64 `json:"balance"`
	CouponRate float64 `json:"coupon_rate"`
}

type Period struct {
	PeriodNum    int     `json:"period"`
	Collections  float64 `json:"collections"`
	Defaults     float64 `json:"defaults"`
	Prepayments  float64 `json:"prepayments"`
	SeniorFee    float64 `json:"senior_fee"`
	ServicerFee  float64 `json:"servicer_fee"`
}

type Input struct {
	Tranches []Tranche `json:"tranches"`
	Periods  []Period  `json:"periods"`
}

type TranchePayment struct {
	ID            string  `json:"id"`
	InterestPaid  float64 `json:"interest_paid"`
	PrincipalPaid float64 `json:"principal_paid"`
	EndingBalance float64 `json:"ending_balance"`
	PIKAmount     float64 `json:"pik_amount"`
	PIKRecovered  float64 `json:"pik_recovered"`
}

type PeriodOutput struct {
	Period         int              `json:"period"`
	TranchePayments []TranchePayment `json:"tranche_payments"`
	ReserveBalance float64          `json:"reserve_balance"`
	Mode           string           `json:"mode"`
	CleanUp        bool             `json:"clean_up"`
}

func r2(v float64) float64 {
	return math.Round(v*100) / 100
}

func main() {
	raw, _ := os.ReadFile("/app/input/collections.json")
	var input Input
	json.Unmarshal(raw, &input)

	originalPool := 0.0
	for i := range input.Tranches {
		originalPool += input.Tranches[i].Balance
	}

	balances := make([]float64, len(input.Tranches))
	for i := range input.Tranches {
		balances[i] = input.Tranches[i].Balance
	}

	cumPIK := make([]float64, len(input.Tranches))

	reserve := 0.0
	reserveTarget := r2(0.02 * originalPool)
	cumDefaults := 0.0
	mode := "sequential"
	modeLocked := false
	stepUpTriggered := false
	var results []PeriodOutput

	for _, p := range input.Periods {
		cumDefaults += p.Defaults
		available := p.Collections - p.Defaults + p.Prepayments

		// step-up: C coupon +1% when cum default rate hits 3%
		cumDefaultRate := cumDefaults / originalPool
		if !stepUpTriggered && cumDefaultRate >= 0.03 {
			stepUpTriggered = true
			for i := range input.Tranches {
				if input.Tranches[i].Class == "C" {
					input.Tranches[i].CouponRate = math.Round((input.Tranches[i].CouponRate+0.01)*10000) / 10000
				}
			}
		}

		// --- Loss allocation (before fees/interest) ---
		// Current pool balance = sum of ALL tranche balances at period start
		currentPoolStart := 0.0
		for i := range balances {
			currentPoolStart += balances[i]
		}
		lossThreshold := r2(0.03 * currentPoolStart)
		if p.Defaults > lossThreshold {
			excess := r2(p.Defaults - lossThreshold)
			// write-down bottom-up: residual(3), C, B, A
			writeOrder := []int{}
			// find residual index
			for i, t := range input.Tranches {
				if t.Class == "residual" {
					writeOrder = append(writeOrder, i)
				}
			}
			// then C, B, A
			for i, t := range input.Tranches {
				if t.Class == "C" {
					writeOrder = append(writeOrder, i)
				}
			}
			for i, t := range input.Tranches {
				if t.Class == "B" {
					writeOrder = append(writeOrder, i)
				}
			}
			for i, t := range input.Tranches {
				if t.Class == "A" {
					writeOrder = append(writeOrder, i)
				}
			}
			for _, idx := range writeOrder {
				if excess <= 0 {
					break
				}
				wd := math.Min(excess, balances[idx])
				wd = r2(wd)
				balances[idx] = r2(balances[idx] - wd)
				excess = r2(excess - wd)
			}
		}

		// fees
		available -= p.SeniorFee
		available -= p.ServicerFee
		available = r2(available)

		// interest
		interestDue := make([]float64, len(input.Tranches))
		for i, t := range input.Tranches {
			if t.Class != "residual" {
				interestDue[i] = r2(balances[i] * t.CouponRate / 12.0)
			}
		}

		interestPaid := make([]float64, len(input.Tranches))
		pikAmounts := make([]float64, len(input.Tranches))
		for i, t := range input.Tranches {
			if t.Class == "residual" {
				continue
			}
			if available >= interestDue[i] {
				interestPaid[i] = interestDue[i]
				available = r2(available - interestDue[i])
			} else {
				interestPaid[i] = r2(available)
				shortfall := r2(interestDue[i] - interestPaid[i])
				pikAmounts[i] = shortfall
				balances[i] = r2(balances[i] + shortfall)
				cumPIK[i] = r2(cumPIK[i] + shortfall)
				available = 0
			}
		}

		// scheduled principal = collections - interest paid - fees - prepayments
		totalInterestPaid := 0.0
		for i := range interestPaid {
			totalInterestPaid += interestPaid[i]
		}
		scheduledPrincipal := r2(p.Collections - totalInterestPaid - p.SeniorFee - p.ServicerFee - p.Prepayments)
		if scheduledPrincipal < 0 {
			scheduledPrincipal = 0
		}

		// triggers
		currentPool := 0.0
		for i := range balances {
			currentPool += balances[i]
		}
		poolFactor := currentPool / originalPool
		abcBalance := 0.0
		for i, t := range input.Tranches {
			if t.Class != "residual" {
				abcBalance += balances[i]
			}
		}
		ocTest := abcBalance < 0.92*currentPool

		allTriggersPass := poolFactor > 0.50 && cumDefaultRate < 0.04 && ocTest

		if !modeLocked {
			if mode == "sequential" && allTriggersPass {
				mode = "pro_rata"
			} else if mode == "pro_rata" && !allTriggersPass {
				mode = "sequential"
				modeLocked = true
			}
		}

		// distribute scheduled principal
		principalPaid := make([]float64, len(input.Tranches))
		schedAvail := math.Min(float64(scheduledPrincipal), available)

		if mode == "sequential" {
			for i, t := range input.Tranches {
				if t.Class == "residual" {
					continue
				}
				pay := math.Min(schedAvail, balances[i])
				pay = r2(pay)
				principalPaid[i] += pay
				balances[i] = r2(balances[i] - pay)
				schedAvail = r2(schedAvail - pay)
				available = r2(available - pay)
			}
		} else {
			totalABC := 0.0
			for i, t := range input.Tranches {
				if t.Class != "residual" {
					totalABC += balances[i]
				}
			}
			if totalABC > 0 {
				for i, t := range input.Tranches {
					if t.Class == "residual" {
						continue
					}
					share := balances[i] / totalABC
					pay := r2(schedAvail * share)
					pay = math.Min(pay, balances[i])
					pay = r2(pay)
					principalPaid[i] += pay
					balances[i] = r2(balances[i] - pay)
					available = r2(available - pay)
				}
			}
		}

		// prepayment principal always pro-rata
		prepayAvail := math.Min(p.Prepayments, available)
		totalABC := 0.0
		for i, t := range input.Tranches {
			if t.Class != "residual" {
				totalABC += balances[i]
			}
		}
		if totalABC > 0 && prepayAvail > 0 {
			for i, t := range input.Tranches {
				if t.Class == "residual" {
					continue
				}
				share := balances[i] / totalABC
				pay := r2(prepayAvail * share)
				pay = math.Min(pay, balances[i])
				pay = r2(pay)
				principalPaid[i] += pay
				balances[i] = r2(balances[i] - pay)
				available = r2(available - pay)
			}
		}

		// reserve trap, then PIK recovery, then turbo
		pikRecovered := make([]float64, len(input.Tranches))
		if available > 0 {
			if reserve < reserveTarget {
				trap := math.Min(available, r2(reserveTarget-reserve))
				reserve = r2(reserve + trap)
				available = r2(available - trap)
			}

			// PIK recovery: A → B → C (after reserve cap reached, before turbo)
			if available > 0 {
				for i, t := range input.Tranches {
					if t.Class == "residual" {
						continue
					}
					if cumPIK[i] > 0 && available > 0 && balances[i] > 0 {
						recovery := math.Min(available, cumPIK[i])
						recovery = math.Min(recovery, balances[i])
						recovery = r2(recovery)
						pikRecovered[i] = recovery
						balances[i] = r2(balances[i] - recovery)
						cumPIK[i] = r2(cumPIK[i] - recovery)
						available = r2(available - recovery)
					}
				}
			}

			// turbo cascades through most senior with balance
			if available > 0 && ocTest {
				for i, t := range input.Tranches {
					if t.Class == "residual" {
						continue
					}
					if balances[i] > 0 && available > 0 {
						turbo := math.Min(available, balances[i])
						turbo = r2(turbo)
						principalPaid[i] += turbo
						balances[i] = r2(balances[i] - turbo)
						available = r2(available - turbo)
					}
				}
			}
		}

		// clean-up
		currentPool = 0.0
		for i := range balances {
			currentPool += balances[i]
		}
		cleanUp := currentPool < 0.10*originalPool && currentPool > 0

		if cleanUp {
			for i := range balances {
				principalPaid[i] += balances[i]
				balances[i] = 0
			}
		}

		payments := make([]TranchePayment, len(input.Tranches))
		for i, t := range input.Tranches {
			payments[i] = TranchePayment{
				ID:            t.ID,
				InterestPaid:  r2(interestPaid[i]),
				PrincipalPaid: r2(principalPaid[i]),
				EndingBalance: r2(balances[i]),
				PIKAmount:     r2(pikAmounts[i]),
				PIKRecovered:  r2(pikRecovered[i]),
			}
		}

		results = append(results, PeriodOutput{
			Period:          p.PeriodNum,
			TranchePayments: payments,
			ReserveBalance:  r2(reserve),
			Mode:            mode,
			CleanUp:         cleanUp,
		})

		if cleanUp {
			break
		}
	}

	out, _ := json.MarshalIndent(results, "", "  ")
	os.MkdirAll("/app/output", 0755)
	os.WriteFile("/app/output/waterfall.json", out, 0644)
}
EOF

cd /app && go mod init waterfall 2>/dev/null || true
cd /app && go build -o /app/waterfall . && /app/waterfall
