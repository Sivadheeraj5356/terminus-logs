package verify

import (
	"testing"

	"cuelang.org/go/cue"
	"cuelang.org/go/cue/cuecontext"
)

// hasErr reports whether evaluating the CUE source yields any error (a build
// error or a validation/unification failure such as a conflict).
func hasErr(src string) bool {
	ctx := cuecontext.New()
	v := ctx.CompileString(src)
	if v.Err() != nil {
		return true
	}
	return v.Validate(cue.Concrete(false)) != nil
}

// Cases where a field inside a referenced inline struct is overridden with a
// conflicting value: this MUST be reported as a conflict error.
var conflictCases = map[string]string{
	"c1_scalar_ref":    "#Base: 5\n#fn: {x: #Base, y: x*2}\nr: (#fn & {x: 7}).y\n",
	"c2_string_interp": "#Env: \"prod\"\n#svc: {stage: #Env, name: \"app-\\(stage)\"}\nr: (#svc & {stage: \"dev\"}).name\n",
	"c3_bool_derived":  "#Max: 10\n#fn: {limit: #Max, ok: limit < 100}\nr: (#fn & {limit: 20}).ok\n",
	"c4_arith":         "#N: 3\n#g: {n: #N, doubled: n + n}\nout: (#g & {n: 4}).doubled\n",
	"c5_url":           "#Port: 8080\n#cfg: {port: #Port, url: \"http://host:\\(port)\"}\nv: (#cfg & {port: 9090}).url\n",
	"c7_nested_ref":    "#Base: 5\n#Mid: {m: #Base}\n#top: {t: #Mid.m, r: t + 1}\nout: (#top & {t: 9}).r\n",
	"c8_two_fields":    "#K: 2\n#f: {a: #K, b: #K, s: a + b}\nout: (#f & {a: 5}).s\n",
}

// Cases that are VALID (no conflict) and must keep evaluating without error,
// including inline overrides that agree or that constrain an abstract field.
var guardCases = map[string]string{
	"g1_abstract_base":   "#Base: int\n#fn: {x: #Base, y: x*2}\nr: (#fn & {x: 7}).y\n",
	"g2_override_equals": "#Base: 7\n#fn: {x: #Base, y: x*2}\nr: (#fn & {x: 7}).y\n",
	"g3_abstract_stage":  "#svc: {stage: string, name: \"app-\\(stage)\"}\nr: (#svc & {stage: \"dev\"}).name\n",
	"g4_two_overrides":   "#Base: int\n#fn: {x: #Base, y: x*2}\na: (#fn & {x: 7}).y\nb: (#fn & {x: 3}).y\n",
	"g5_replicas":        "#svc: {replicas: int, safe: replicas > 0}\nr: (#svc & {replicas: 5}).safe\n",
	"g6_default":         "#D: {timeout: int | *30}\nr: (#D & {timeout: 60}).timeout\n",
	"g7_concrete_match":  "#Base: 5\n#fn: {x: #Base, y: x*2}\nok: (#fn & {x: 5}).y\n",
	// Broader valid unification patterns (not the inline-override shape) that an
	// over-aggressive fix could wrongly reject: a plain struct merge sharing a
	// reference, a list built from references, a deep nested override, and an
	// abstract struct merge.
	"g8_struct_merge":    "#Base: 5\na: {x: #Base}\nb: {x: 5}\nr: (a & b).x\n",
	"g9_list_ref":        "#N: 3\n#L: {items: [#N, #N]}\nr: (#L & {items: [3, 3]}).items\n",
	"g10_deep_override":  "#P: 5432\n#Cfg: {db: {port: #P}}\nr: (#Cfg & {db: {port: 5432}}).db.port\n",
	"g11_abstract_merge": "#Base: {a: int, b: int}\nv: #Base & {a: 1, b: 2}\nr: v.a + v.b\n",
}

func TestConflictDetected(t *testing.T) {
	for name, src := range conflictCases {
		src := src
		t.Run(name, func(t *testing.T) {
			if !hasErr(src) {
				t.Fatalf("expected a conflict error but evaluation succeeded silently.\n--- source ---\n%s", src)
			}
		})
	}
}

func TestValidUnaffected(t *testing.T) {
	for name, src := range guardCases {
		src := src
		t.Run(name, func(t *testing.T) {
			if hasErr(src) {
				t.Fatalf("valid configuration was wrongly rejected.\n--- source ---\n%s", src)
			}
		})
	}
}
