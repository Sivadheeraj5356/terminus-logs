package export

import (
	"encoding/csv"
	"fmt"
	"io"

	"ra.local/field/internal/domain"
)

func WriteResiduals(writer io.Writer, rows []domain.Residual) error {
	csvWriter := csv.NewWriter(writer)
	if err := csvWriter.Write([]string{"observation_id", "peptide", "residual"}); err != nil {
		return err
	}
	for _, row := range rows {
		if err := csvWriter.Write([]string{
			row.ObservationID, row.Peptide, fmt.Sprintf("%.17g", row.Residual),
		}); err != nil {
			return err
		}
	}
	csvWriter.Flush()
	return csvWriter.Error()
}
