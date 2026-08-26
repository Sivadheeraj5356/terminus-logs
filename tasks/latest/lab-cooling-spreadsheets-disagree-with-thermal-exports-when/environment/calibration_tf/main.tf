terraform {
  required_version = ">= 1.5.0"
}

variable "camera_profiles" {
  type = map(object({
    gain                  = number
    offset                = number
    emissivity_correction = number
    dark_offset_base      = number
    dark_offset_rate      = number
  }))
  default = {
    "cam-ir7" = {
      gain                  = 0.042
      offset                = -273.15
      emissivity_correction = 1.2
      dark_offset_base      = 1800.0
      dark_offset_rate      = 0.35
    }
    "cam-ir9" = {
      gain                  = 0.039
      offset                = -272.8
      emissivity_correction = 0.9
      dark_offset_base      = 2100.0
      dark_offset_rate      = 0.28
    }
    "cam-ir12" = {
      gain                  = 0.037
      offset                = -272.5
      emissivity_correction = 1.5
      dark_offset_base      = 1950.0
      dark_offset_rate      = 0.32
    }
  }
}

output "calibration_constants" {
  value = var.camera_profiles
}
