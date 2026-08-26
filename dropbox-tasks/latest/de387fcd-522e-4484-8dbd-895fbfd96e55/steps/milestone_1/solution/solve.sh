#!/bin/bash
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd /app

ls docs/
head -n 90 docs/pricing-policy.md
grep -nE 'Gson|pretty|netRecovery|quotaCredit|sort|generatedAt|policies|summary|adjustmentRate' \
    docs/pricing-policy.md docs/quota-addendum.md docs/premium-holdback-addendum.md docs/rounding-schedule.md docs/config-keys.md

grep -nE 'override|minimum\.|adjustment\.tier|catastrophe\.credit' \
    coinsurance-core/src/main/java/com/coinsurancerecovery/core/CoinsuranceConfigLoader.java || true
grep -nE 'approved|meetsMinimum|equalsIgnoreCase' \
    coinsurance-core/src/main/java/com/coinsurancerecovery/core/EligibilityRules.java || true
grep -nE 'sort|tierAdjustment|quotaCredit|netRecovery' \
    coinsurance-engine/src/main/java/com/coinsurancerecovery/engine/CoinsuranceProcessor.java \
    coinsurance-engine/src/main/java/com/coinsurancerecovery/engine/TierAdjustmentEngine.java \
    coinsurance-engine/src/main/java/com/coinsurancerecovery/engine/QuotaCreditEngine.java || true
grep -nE 'Gson|generatedAt|processingFee|totalRecovery|PremiumRetention' \
    coinsurance-report/src/main/java/com/coinsurancerecovery/report/ReportGenerator.java \
    coinsurance-report/src/main/java/com/coinsurancerecovery/report/FinancePolicy.java \
    coinsurance-engine/src/main/java/com/coinsurancerecovery/engine/PremiumHoldbackCalculator.java || true

mvn -q -B -o test
if test -f output/coinsurance-report.json; then
  head -n 25 output/coinsurance-report.json
fi

bash "${SCRIPT_DIR}/solve1.sh"
