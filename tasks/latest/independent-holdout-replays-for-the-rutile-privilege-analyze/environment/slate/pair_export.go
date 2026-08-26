package slate

import "rutile/internal/types"

func RolePairs(assume []types.AssumeRow) [][2]string {
    return op_b(assume)
}
