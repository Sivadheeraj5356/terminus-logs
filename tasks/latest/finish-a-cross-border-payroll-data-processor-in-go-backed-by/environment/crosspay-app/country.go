package main

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"sync"
)

// countryDatasetPath is the bundled reference dataset of country metadata. It is
// a local, offline file shipped with the app; there is no network access. Each
// record carries an ISO 3166-1 alpha-2 code, the country's primary currency and
// its continent.
const countryDatasetPath = "/app/reference/countries.json"

// ErrCountryNotFound is returned when the dataset has no such country code.
var ErrCountryNotFound = fmt.Errorf("not_found")

// countryRecord is one row of the bundled dataset.
type countryRecord struct {
	Code      string `json:"code"`
	Name      string `json:"name"`
	Currency  string `json:"currency"`
	Continent string `json:"continent"`
}

// countryFile is the top-level shape of the dataset file.
type countryFile struct {
	Countries []countryRecord `json:"countries"`
}

var (
	datasetOnce sync.Once
	datasetByCC map[string]countryRecord
	datasetErr  error
)

// loadDataset reads and indexes the bundled dataset exactly once. The currency
// field may be a comma-separated list; the primary (first) currency code is
// kept.
func loadDataset() {
	raw, err := os.ReadFile(countryDatasetPath)
	if err != nil {
		datasetErr = fmt.Errorf("read dataset: %w", err)
		return
	}
	var cf countryFile
	if err := json.Unmarshal(raw, &cf); err != nil {
		datasetErr = fmt.Errorf("parse dataset: %w", err)
		return
	}
	datasetByCC = make(map[string]countryRecord, len(cf.Countries))
	for _, rec := range cf.Countries {
		cur := rec.Currency
		if i := strings.IndexByte(cur, ','); i >= 0 {
			cur = cur[:i]
		}
		rec.Currency = strings.TrimSpace(cur)
		rec.Code = strings.ToUpper(strings.TrimSpace(rec.Code))
		datasetByCC[rec.Code] = rec
	}
}

// LoadCountry looks up the metadata for an ISO 3166-1 alpha-2 code in the
// bundled dataset. Returns ErrCountryNotFound when the dataset has no such
// country.
func LoadCountry(code string) (*Country, error) {
	datasetOnce.Do(loadDataset)
	if datasetErr != nil {
		return nil, datasetErr
	}
	code = strings.ToUpper(strings.TrimSpace(code))
	rec, ok := datasetByCC[code]
	if !ok {
		return nil, ErrCountryNotFound
	}
	return &Country{
		Code:      code,
		Currency:  rec.Currency,
		Continent: rec.Continent,
		Name:      rec.Name,
	}, nil
}
