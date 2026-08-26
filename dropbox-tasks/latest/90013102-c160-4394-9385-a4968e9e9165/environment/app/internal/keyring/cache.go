package keyring

import "sync"

type cacheEntry struct {
	secret          []byte
	allowedVersions []int
	catalogDigest   string
}

// AuthorityCache caches verification secrets by key identity.
type AuthorityCache struct {
	mu      sync.RWMutex
	entries map[string]*cacheEntry
}

func NewAuthorityCache() *AuthorityCache {
	return &AuthorityCache{entries: make(map[string]*cacheEntry)}
}

func cacheKey(tenant, keyID string, keyEpoch int) string {
	return tenant + "|" + keyID + "|" + itoa(keyEpoch)
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	var buf [20]byte
	i := len(buf)
	for n > 0 {
		i--
		buf[i] = byte('0' + n%10)
		n /= 10
	}
	return string(buf[i:])
}

func (c *AuthorityCache) Get(tenant, keyID string, keyEpoch int) ([]byte, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	e, ok := c.entries[cacheKey(tenant, keyID, keyEpoch)]
	if !ok {
		return nil, false
	}
	return e.secret, true
}

func (c *AuthorityCache) Put(tenant, keyID string, keyEpoch int, secret []byte, versions []int, catalogDigest string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	cp := append([]byte(nil), secret...)
	c.entries[cacheKey(tenant, keyID, keyEpoch)] = &cacheEntry{
		secret:          cp,
		allowedVersions: append([]int(nil), versions...),
		catalogDigest:   catalogDigest,
	}
}

func (c *AuthorityCache) Clear() {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.entries = make(map[string]*cacheEntry)
}
