terraform {
  # terraform_data is a built-in resource (no external provider needed), so
  # `terraform init` / `terraform apply` run fully offline.
  required_version = ">= 1.4"
}

variable "fixtures_dir" {
  type    = string
  default = "/app/data/fixtures"
}

variable "cards_dir" {
  type    = string
  default = "/app/data/modelcards"
}

variable "notebook" {
  type    = string
  default = "/app/docs/reefbox-field-notebook.md"
}

variable "out_dir" {
  type    = string
  default = "/app/out"
}

# Orchestration layer: on every `terraform apply`, run the calibration pipeline,
# which decodes the PNG calibration blocks, merges the YAML model cards, and
# writes ${var.out_dir}/inference_manifest.json.
resource "terraform_data" "manifest" {
  triggers_replace = [timestamp()]

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command = join(" ", [
      "FIXTURES_DIR='${var.fixtures_dir}'",
      "CARDS_DIR='${var.cards_dir}'",
      "NOTEBOOK='${var.notebook}'",
      "OUT_DIR='${var.out_dir}'",
      "bash '${path.module}/pipeline/build_manifest.sh'",
    ])
  }
}
