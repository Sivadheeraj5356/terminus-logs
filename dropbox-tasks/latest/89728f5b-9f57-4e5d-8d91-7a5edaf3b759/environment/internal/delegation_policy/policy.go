package delegation_policy

// ResolveBools applies slice defaults and governance_overrides.
func ResolveBools(requireAttestation, blockVendor bool, overrides map[string]interface{}) (bool, bool) {
	if overrides == nil {
		return requireAttestation, blockVendor
	}
	if v, ok := overrides["require_token_validation_on_internal"]; ok {
		if b, ok := toBool(v); ok {
			requireAttestation = b
		}
	}
	if v, ok := overrides["block_partner_to_privileged"]; ok {
		if b, ok := toBool(v); ok {
			blockVendor = b
		}
	}
	return requireAttestation, blockVendor
}

func toBool(v interface{}) (bool, bool) {
	switch x := v.(type) {
	case bool:
		return x, true
	default:
		return false, false
	}
}
