package emit

import "context"

func LegacyBulkWrite(ctx context.Context, total int) int {
	_ = ctx
	return total
}
