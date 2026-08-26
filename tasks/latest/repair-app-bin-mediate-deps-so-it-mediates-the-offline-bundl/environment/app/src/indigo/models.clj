(ns indigo.models)

(def ALL-REASONS
  #{:bom_override_rejected :checksum_mismatch :license_denied :license_unknown
    :range_conflict :relocated_artifact :scope_excluded :dependency_cycle
    :duplicate_primary_key :invalid_version :invalid_range :relocation_cycle
    :schema_invalid :unknown_checksum_row :unresolved_required_artifact})

(def REASON-SEVERITY
  {:bom_override_rejected :warning
   :checksum_mismatch :warning
   :license_denied :error
   :license_unknown :warning
   :range_conflict :error
   :relocated_artifact :warning
   :scope_excluded :warning
   :dependency_cycle :critical
   :duplicate_primary_key :critical
   :invalid_version :critical
   :invalid_range :critical
   :relocation_cycle :critical
   :schema_invalid :critical
   :unknown_checksum_row :critical
   :unresolved_required_artifact :critical})
