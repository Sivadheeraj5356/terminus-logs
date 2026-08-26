package pond

// Arm is one brine-lane polygon edge in the lane snapshot.
type Arm struct {
	ArmKey   string  `json:"arm_key"`
	ArmID    int     `json:"arm_id"`
	ArmLabel int     `json:"arm_label"`
	BaseFront float64 `json:"base_front"`
	Sealed   bool    `json:"sealed"`
}
