# Production deployment defaults for the media moderation API.
#
# NOTE: these values were lifted from the staging environment during the
# launch push and mirror config/inference.js. They still need a security
# review before this service faces public traffic.

debug_inference_enabled = true

cors_allowed_origins = ["*"]

max_upload_bytes = 104857600

telemetry_redaction_enabled = false

telemetry_redacted_fields = []

moderation_threshold_safe       = 0.15
moderation_threshold_suggestive = 0.35
moderation_threshold_explicit   = 0.4
