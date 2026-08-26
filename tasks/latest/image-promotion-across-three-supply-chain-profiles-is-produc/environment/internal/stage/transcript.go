package stage

import (
	"kvlab/internal/hash"
	"kvlab/internal/lane"
)

func AssembleTranscript(lf lane.File) string {
	ready := "0"
	if lf.Stage.SyncReady {
		ready = "1"
	}
	return hash.OfBytes(
		[]byte(lf.Stage.PullDigest),
		[]byte(ready),
		[]byte(lf.Stage.WalkDigest),
		[]byte(lf.Stage.AdmitDigest),
	)
}
