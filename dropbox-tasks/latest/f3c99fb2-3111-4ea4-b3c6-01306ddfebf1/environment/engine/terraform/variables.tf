variable "debug_inference_enabled" {
  description = "Whether the unauthenticated /debug/infer route is served."
  type        = bool
}

variable "cors_allowed_origins" {
  description = "Origins permitted to call the moderation API via CORS."
  type        = list(string)
}

variable "max_upload_bytes" {
  description = "Maximum accepted size (in bytes) for an uploaded image."
  type        = number
}

variable "telemetry_redaction_enabled" {
  description = "Whether telemetry redacts PII from recorded request payloads."
  type        = bool
}

variable "telemetry_redacted_fields" {
  description = "Request fields replaced before telemetry is emitted."
  type        = list(string)
}

variable "moderation_threshold_safe" {
  description = "Confidence threshold for the 'safe' label."
  type        = number
}

variable "moderation_threshold_suggestive" {
  description = "Confidence threshold for the 'suggestive' label."
  type        = number
}

variable "moderation_threshold_explicit" {
  description = "Confidence threshold for the 'explicit' label."
  type        = number
}
