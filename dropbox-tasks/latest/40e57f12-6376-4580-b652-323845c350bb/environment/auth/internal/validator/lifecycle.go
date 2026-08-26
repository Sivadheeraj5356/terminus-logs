package validator

import (
	"errors"

	"github.com/golang-jwt/jwt/v5"

	"github.com/acme/auth/internal/jwk"
	"github.com/acme/auth/internal/ledger"
)

type RevocationChecker interface {
	IsRevoked(jti string) (bool, error)
}

type LifecycleValidator struct {
	inner *Validator
	ledger RevocationChecker
}

func NewLifecycle(keys *jwk.Set, led *ledger.Ledger) *LifecycleValidator {
	return &LifecycleValidator{
		inner:  New(keys),
		ledger: led,
	}
}

func (v *LifecycleValidator) Validate(tokenStr string) (*jwt.Token, error) {
	token, err := v.inner.Validate(tokenStr)
	if err != nil {
		return nil, err
	}
	jti, err := JTI(token)
	if err != nil {
		return nil, err
	}
	revoked, err := v.ledger.IsRevoked(jti)
	if err != nil {
		return nil, err
	}
	if revoked {
		return nil, ErrInvalidToken
	}
	return token, nil
}

var ErrRevoked = errors.New("token revoked")
