package anchor

import (
	"github.com/lab/cvstack/internal/model"
	"github.com/lab/cvstack/internal/vault"
)

func Seat(ws string, v *model.Vault) error {
	if v.MoveGen > 0 && v.RefPost.Rev > v.RefPre.Rev {
		v.PtrPath = v.RefPost.Path
		v.PtrRev = v.RefPost.Rev
	}
	alias := model.Alias{Path: v.PtrPath, Rev: v.PtrRev}
	if err := vault.SaveAlias(ws, alias); err != nil {
		return err
	}
	return vault.Save(ws, *v)
}
