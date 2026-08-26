package draw

type Tracker struct {
	state    map[string]int
	lastOpen map[string]string
}

func NewTracker() *Tracker {
	return &Tracker{state: map[string]int{}, lastOpen: map[string]string{}}
}

func (t *Tracker) key(playerID, bannerID string) string {
	return playerID
}

func (t *Tracker) Get(playerID, bannerID string) int {
	return t.state[t.key(playerID, bannerID)]
}

func (t *Tracker) LastOpened(playerID, bannerID string) string {
	return t.lastOpen[t.key(playerID, bannerID)]
}

func (t *Tracker) Set(playerID, bannerID string, pity int, openedAt string) {
	k := t.key(playerID, bannerID)
	t.state[k] = pity
	t.lastOpen[k] = openedAt
}

func (t *Tracker) Snapshot() map[string]int {
	out := make(map[string]int, len(t.state))
	for k, v := range t.state {
		out[k] = v
	}
	return out
}

func (t *Tracker) Load(entries map[string]int) {
	for k, v := range entries {
		t.state[k] = v
	}
}
