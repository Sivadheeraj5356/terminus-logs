package flint

import "rutile/internal/types"

func Allows(constraints []types.ConstraintRow, srcLevel, dstLevel int) bool {
    return op_c(constraints, srcLevel, dstLevel)
}
