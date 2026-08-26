package api

type Region struct { RegionID string `json:"region_id"`; EquityFloor int `json:"equity_floor"`; DemandDose1 int `json:"demand_dose1"`; DemandDose2 int `json:"demand_dose2"`; StorageTemp string `json:"storage_temp"` }
type Lot struct { LotID string `json:"lot_id"`; ReceiveDay int `json:"receive_day"`; ExpiryDay int `json:"expiry_day"`; TempBand string `json:"temp_band"`; Doses int `json:"doses"` }
type Route struct { LegID string `json:"leg_id"`; RegionID string `json:"region_id"`; PalletID string `json:"pallet_id"`; DepartDay int `json:"depart_day"`; ArriveDay int `json:"arrive_day"`; TempBand string `json:"temp_band"`; LaneHours int `json:"lane_hours"`; CustomsDelayDays int `json:"customs_delay_days"` }
type Clinic struct { ClinicID string `json:"clinic_id"`; RegionID string `json:"region_id"`; MinGapDays int `json:"min_gap_days"` }
type DemandRow struct { RegionID string `json:"region_id"`; Wave int `json:"wave"`; Dose1 int `json:"dose1"`; Dose2 int `json:"dose2"` }
type Config struct { ReserveDoses int `json:"reserve_doses"`; VialSize int `json:"vial_size"` }
type LotAssignment struct { RegionID string `json:"region_id"`; LotID string `json:"lot_id"`; Doses int `json:"doses"`; TempBand string `json:"temp_band"`; PalletID string `json:"pallet_id"` }
type RegionCoverage struct { RegionID string `json:"region_id"`; Delivered int `json:"delivered"`; Need int `json:"need"`; CoverageRatio float64 `json:"coverage_ratio"` }
type AllocationPlan struct { Wave int `json:"wave"`; LotAssignments []LotAssignment `json:"lot_assignments"`; RegionCoverage []RegionCoverage `json:"region_coverage"`; EquityMet bool `json:"equity_met"`; PlanDigestHex string `json:"plan_digest_hex"` }
