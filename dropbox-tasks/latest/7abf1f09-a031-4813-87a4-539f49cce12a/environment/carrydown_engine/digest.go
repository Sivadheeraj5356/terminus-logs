package main

import (
	"crypto/sha256"
	"encoding/hex"
	"strconv"
)

func reportDigest(rows []TenantLedger) string {
	var blob []byte
	for _, x := range rows {
		blob = append(blob, []byte(x.TenantID)...)
		blob = append(blob, '|')
		blob = append(blob, []byte(strconv.FormatInt(x.TotalCharge, 10))...)
		blob = append(blob, '|')
		blob = append(blob, []byte(strconv.FormatInt(x.NetUsage, 10))...)
		blob = append(blob, '|')
		blob = append(blob, []byte(strconv.FormatInt(x.SharedAllocated, 10))...)
		blob = append(blob, '\n')
	}
	sum := sha256.Sum256(blob)
	return hex.EncodeToString(sum[:])
}
