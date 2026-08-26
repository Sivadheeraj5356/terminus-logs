package vault

import (
	"path/filepath"

	cvio "github.com/lab/cvstack/internal/io"
	"github.com/lab/cvstack/internal/model"
)

func Load(ws string) (model.Vault, error) {
	var v model.Vault
	err := cvio.ReadJSON(filepath.Join(ws, "state", "vault.json"), &v)
	return v, err
}

func Save(ws string, v model.Vault) error {
	return cvio.WriteJSON(filepath.Join(ws, "state", "vault.json"), v)
}

func LoadAlias(ws string) (model.Alias, error) {
	var a model.Alias
	err := cvio.ReadJSON(filepath.Join(ws, "maps", "origin_alias.json"), &a)
	return a, err
}

func SaveAlias(ws string, a model.Alias) error {
	return cvio.WriteJSON(filepath.Join(ws, "maps", "origin_alias.json"), a)
}

func LoadActive(ws string) (model.Ref, error) {
	var r model.Ref
	err := cvio.ReadJSON(filepath.Join(ws, "refs", "active.json"), &r)
	return r, err
}

func SaveActive(ws string, r model.Ref) error {
	return cvio.WriteJSON(filepath.Join(ws, "refs", "active.json"), r)
}

func LoadTap(ws string) (model.Tap, error) {
	var t model.Tap
	err := cvio.ReadJSON(filepath.Join(ws, "state", "tap.json"), &t)
	return t, err
}

func SaveTap(ws string, t model.Tap) error {
	return cvio.WriteJSON(filepath.Join(ws, "state", "tap.json"), t)
}
