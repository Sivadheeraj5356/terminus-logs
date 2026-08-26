package decoy

// LegacyEntryHint mirrors retired v1 level-one entry detection.
func LegacyEntryHint(level int) bool {
    return level == 1
}
