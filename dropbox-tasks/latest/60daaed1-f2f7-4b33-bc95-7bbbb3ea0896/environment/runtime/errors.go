package main

import (
	"encoding/json"
	"net/http"
)

type apiErrorEnvelope struct {
	Error apiError `json:"error"`
}

type apiError struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

func writeJSON(w http.ResponseWriter, status int, body any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(body)
}

func writeUnauthorized(w http.ResponseWriter) {
	writeJSON(w, http.StatusUnauthorized, apiErrorEnvelope{Error: apiError{
		Code:    "unauthorized",
		Message: "missing or invalid bearer token",
	}})
}

func writeNotFound(w http.ResponseWriter) {
	writeJSON(w, http.StatusNotFound, apiErrorEnvelope{Error: apiError{
		Code:    "not_found",
		Message: "route not found",
	}})
}

func writeMethodNotAllowed(w http.ResponseWriter) {
	writeJSON(w, http.StatusMethodNotAllowed, apiErrorEnvelope{Error: apiError{
		Code:    "method_not_allowed",
		Message: "method not allowed",
	}})
}
