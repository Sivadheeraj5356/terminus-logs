package lockctx

import (
	"os"
	"path/filepath"
	"sync"
)

// Context tracks layered view roots and open slot handles for the audit driver.
type Context struct {
	Workspace string
	HostView  string
	PeerView  string
	Published string
	Archive   string
	Fixtures  string

	mu      sync.Mutex
	pinGen  int
	pinPath string
	active  *Handle
}

// Handle wraps a pinned open file descriptor against a published slot.
type Handle struct {
	Gen  int
	Path string
	File *os.File
}

// New builds a lock context from workspace and fixture roots.
func New(workspace, fixtures string) *Context {
	base := filepath.Clean(workspace)
	return &Context{
		Workspace: base,
		HostView:  filepath.Join(base, "views", "host"),
		PeerView:  filepath.Join(base, "views", "peer"),
		Published: filepath.Join(base, "published"),
		Archive:   filepath.Join(base, "archive"),
		Fixtures:  filepath.Clean(fixtures),
	}
}

// Reset clears cached handles between matrix rows.
func (c *Context) Reset() {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.active != nil && c.active.File != nil {
		_ = c.active.File.Close()
	}
	c.active = nil
	c.pinGen = 0
	c.pinPath = ""
}

// ActiveGen returns the slice counter bound to the current slot handle.
func (c *Context) ActiveGen() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.active != nil {
		return c.active.Gen
	}
	return c.pinGen
}

// SetActive records the handle chosen by op_a for downstream readers.
func (c *Context) SetActive(h *Handle) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.active = h
	if h != nil {
		c.pinGen = h.Gen
		c.pinPath = h.Path
	}
}

// PinnedPath returns the pathname currently held by the open table.
func (c *Context) PinnedPath() string {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.pinPath
}
