package validator

import (
	"errors"
	"fmt"

	"github.com/golang-jwt/jwt/v5"

	"github.com/acme/auth/internal/jwk"
)

var ErrInvalidToken = errors.New("invalid token")

type Validator struct {
	keys *jwk.Set
}

func New(keys *jwk.Set) *Validator {
	return &Validator{keys: keys}
}

func (v *Validator) Validate(tokenStr string) (*jwt.Token, error) {
	token, err := jwt.Parse(tokenStr, func(t *jwt.Token) (any, error) {
		if t.Method.Alg() != jwt.SigningMethodEdDSA.Alg() {
			return nil, fmt.Errorf("unexpected alg %s", t.Method.Alg())
		}
		kid, _ := t.Header["kid"].(string)
		if kid == "" {
			return nil, errors.New("missing kid")
		}
		pub, ok := v.keys.Lookup(kid)
		if !ok {
			return nil, fmt.Errorf("unknown kid %s", kid)
		}
		return pub, nil
	}, jwt.WithValidMethods([]string{jwt.SigningMethodEdDSA.Alg()}))
	if err != nil {
		return nil, ErrInvalidToken
	}
	if !token.Valid {
		return nil, ErrInvalidToken
	}
	return token, nil
}

func JTI(token *jwt.Token) (string, error) {
	claims, ok := token.Claims.(jwt.MapClaims)
	if !ok {
		return "", ErrInvalidToken
	}
	jti, _ := claims["jti"].(string)
	if jti == "" {
		return "", ErrInvalidToken
	}
	return jti, nil
}
