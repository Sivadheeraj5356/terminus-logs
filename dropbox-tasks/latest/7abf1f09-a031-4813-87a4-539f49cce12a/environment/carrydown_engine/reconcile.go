package main

func tenantTotal(net, shared int64) int64 {
	return net + shared
}

func sumTotalBillable(rows []TenantLedger) int64 {
	var s int64
	for _, x := range rows {
		s += x.TotalCharge
	}
	return s
}
