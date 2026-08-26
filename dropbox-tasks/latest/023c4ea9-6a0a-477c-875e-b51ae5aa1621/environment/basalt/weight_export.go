package basalt

import "rutile/internal/types"

func UsageWeight(usage []types.UsageRow, src, dst string) int {
    return op_e(usage, src, dst)
}
