package config

import (
	"os"
	"os/signal"
	"syscall"

	"sigproxy/internal/keyring"
)

type Runtime struct {
	Config  *ProxyConfig
	Catalog *ProfileCatalog
	Keyring *keyring.Keyring
	Cache   *keyring.AuthorityCache
}

func Reload(cfgPath, profilesDir, keyringPath string, rt *Runtime) error {
	cfg, err := Load(cfgPath)
	if err != nil {
		return err
	}
	cat, err := LoadProfileCatalog(profilesDir)
	if err != nil {
		return err
	}
	kr, err := keyring.Load(keyringPath)
	if err != nil {
		return err
	}
	rt.Config = cfg
	rt.Catalog = cat
	rt.Keyring = kr
	return nil
}

func InstallSIGHUPHandler(rt *Runtime, cfgPath, profilesDir, keyringPath string) {
	ch := make(chan os.Signal, 1)
	signal.Notify(ch, syscall.SIGHUP)
	go func() {
		for range ch {
			_ = Reload(cfgPath, profilesDir, keyringPath, rt)
		}
	}()
}
