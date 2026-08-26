variable "corpus_dir" {
  type        = string
  description = "Directory containing gdb/ and valgrind/ crash logs to triage."
}

variable "output_dir" {
  type        = string
  default     = ""
  description = "Where triage_report.json is written. Defaults to <module>/out."
}

variable "severity_gate" {
  type        = string
  default     = "high"
  description = "Applying the module fails when a finding at or above this severity exists."
}

variable "redaction_salt" {
  type        = string
  default     = "vaultseal"
  description = "Salt mixed into key fingerprints."
}
