package validator

import (
	"errors"

	"github.com/golang-jwt/jwt/v5"

	"github.com/acme/auth/internal/clock"
	"github.com/acme/auth/internal/jwk"
	"github.com/acme/auth/internal/ledger"
)

type RevocationChecker interface {
	IsRevoked(jti string) (bool, error)
}

type LifecycleValidator struct {
	inner  *Validator
	ledger RevocationChecker
	clock  *clock.Clock
}

func NewLifecycle(keys *jwk.Set, led *ledger.Ledger, clk *clock.Clock) *LifecycleValidator {
	return &LifecycleValidator{
		inner:  New(keys),
		ledger: led,
		clock:  clk,
	}
}

func (v *LifecycleValidator) Validate(tokenStr string) (*jwt.Token, error) {
	token, err := v.inner.Validate(tokenStr)
	if err != nil {
		return nil, err
	}
	claims, ok := token.Claims.(jwt.MapClaims)
	if !ok {
		return nil, ErrInvalidToken
	}
	if exp, ok := claims["exp"].(float64); ok && int64(exp) < v.clock.NowUnix() {
		return nil, ErrInvalidToken
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
