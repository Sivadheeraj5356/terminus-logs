package graph

type Job struct {
	Spec       JobSpec
	ReadyTick  int
	StartTick  int
	FinishTick int
	QueueWait  int
	Running    bool
	Queued     bool
	Node       int
}

func Materialize(spec GraphSpec) ([]*Job, error) {
	out := make([]*Job, 0, len(spec.Jobs))
	for _, js := range spec.Jobs {
		out = append(out, &Job{
			Spec:       js,
			ReadyTick:  -1,
			StartTick:  -1,
			FinishTick: -1,
		})
	}
	return out, nil
}

func ByID(jobs []*Job) map[string]*Job {
	m := make(map[string]*Job, len(jobs))
	for _, j := range jobs {
		m[j.Spec.JobID] = j
	}
	return m
}
