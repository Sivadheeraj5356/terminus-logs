package api

func OpenAPIDoc() map[string]any {
	return map[string]any{
		"openapi": "3.1.0",
		"info": map[string]any{
			"title":   "Fleet Build Gate API",
			"version": "1.0.0",
		},
		"paths": map[string]any{
			"/health": map[string]any{
				"get": map[string]any{"summary": "Health check"},
			},
			"/v1/build-plan": map[string]any{
				"post": map[string]any{"summary": "Compute module build order"},
			},
			"/v1/build-attest": map[string]any{
				"post": map[string]any{"summary": "Attest build plan digest and seal"},
			},
		},
	}
}
