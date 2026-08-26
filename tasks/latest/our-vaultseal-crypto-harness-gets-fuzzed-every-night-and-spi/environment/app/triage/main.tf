terraform {
  required_version = ">= 1.6.0"
  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "2.5.1"
    }
  }
}

locals {
  output_dir = var.output_dir != "" ? var.output_dir : "${path.module}/out"
}

# Materialize the analysis script into the run/output area.
resource "local_file" "analyzer" {
  content         = file("${path.module}/scripts/analyze.py")
  filename        = "${local.output_dir}/analyze.py"
  file_permission = "0755"
}

# Run the offline analysis. A gated corpus makes the analysis exit non-zero,
# which fails `terraform apply` after the report has already been written.
resource "terraform_data" "triage" {
  triggers_replace = {
    script = filesha256("${path.module}/scripts/analyze.py")
    corpus = var.corpus_dir
    gate   = var.severity_gate
    salt   = var.redaction_salt
  }

  provisioner "local-exec" {
    command = "python3 '${local_file.analyzer.filename}' --corpus-dir '${var.corpus_dir}' --output-dir '${local.output_dir}' --severity-gate '${var.severity_gate}' --redaction-salt '${var.redaction_salt}'"
  }
}
