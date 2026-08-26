(ns indigo.loader
  (:require [clojure.java.io :as io]
            [indigo.checksums :as checksums]
            [indigo.csv-io :as csv-io]
            [indigo.edn-io :as edn-io]
            [indigo.ranges :as ranges]
            [indigo.relocation :as relocation]
            [indigo.version :as version]))

(def RELOCATION-HEADER ["from_coord" "to_coord" "reason"])
(def CHECKSUMS-HEADER ["coord" "version" "sha256"])
(def LICENSES-HEADER ["license" "status"])

(def REQUIRED-CONFIG-KEYS
  #{:run-id :scope-order :include-scopes :optional-default :checksum-mode :cycle-mode})

(defn data-file [data-dir name]
  (io/file data-dir name))

(def DEFAULT-CONFIG
  '{:run-id "indigo-default"
    :scope-order [:compile :runtime :test]
    :include-scopes #{:compile :runtime}
    :optional-default false
    :checksum-mode :report
    :cycle-mode :fatal})

(defn- read-optional-csv [path header]
  (if (.exists (io/file path))
    (csv-io/read-csv-file path)
    {:header header :rows []}))

(defn- read-config [data-dir]
  (let [path (data-file data-dir "mediation_config.edn")]
    (if (.exists path)
      (edn-io/read-edn-file path)
      DEFAULT-CONFIG)))

(defn fatal [reason detail]
  {:fatal reason :detail detail})

(defn- header-valid? [actual expected]
  (= (vec actual) (vec expected)))

(defn- valid-scope? [s]
  (contains? #{:compile :runtime :test} s))

(defn- valid-version-spec? [s]
  (or (version/valid-version? s) (some? (ranges/parse-range s))))

(defn validate-config [config]
  (cond
    (not (map? config)) (fatal :schema_invalid "mediation_config.edn must be a map")
    (not (every? #(contains? config %) REQUIRED-CONFIG-KEYS)) (fatal :schema_invalid "missing required mediation_config keys")
    (not (every? valid-scope? (:scope-order config))) (fatal :schema_invalid "invalid scope-order entry")
    (not (and (set? (:include-scopes config)) (every? valid-scope? (:include-scopes config))))
    (fatal :schema_invalid "invalid include-scopes")
    (not (contains? #{:report :fatal} (:checksum-mode config))) (fatal :schema_invalid "invalid checksum-mode")
    (not (contains? #{:fatal :report} (:cycle-mode config))) (fatal :schema_invalid "invalid cycle-mode")
    :else nil))

(defn validate-roots [roots]
  (when (not (sequential? roots))
    (fatal :schema_invalid "roots.edn must be a vector"))
  (loop [items roots seen #{}]
    (if (empty? items)
      nil
      (let [{:keys [coord version scope optional exclusions]} (first items)]
        (or
         (when (not (version/valid-coord? coord))
           (fatal :invalid_version (str "invalid root coord " coord)))
         (when (contains? seen coord)
           (fatal :duplicate_primary_key (str "duplicate root coord " coord)))
         (when (not (valid-version-spec? version))
           (fatal :invalid_range (str "invalid root version " version)))
         (when (not (valid-scope? scope))
           (fatal :schema_invalid (str "invalid root scope " scope)))
         (when (not (boolean? optional))
           (fatal :schema_invalid "root optional must be boolean"))
         (when (not (sequential? exclusions))
           (fatal :schema_invalid "root exclusions must be a vector"))
         (when (some #(not (version/valid-coord? %)) exclusions)
           (fatal :schema_invalid "invalid exclusion coordinate"))
         (recur (rest items) (conj seen coord)))))))

(defn- validate-artifact [coord ver artifact]
  (cond
    (not (version/valid-version? ver)) (fatal :invalid_version (str "invalid version " ver " for " coord))
    (not (map? artifact)) (fatal :schema_invalid (str "artifact must be a map for " coord ":" ver))
    (not (string? (:jar artifact))) (fatal :schema_invalid (str "missing jar for " coord ":" ver))
    (not (string? (:sha256 artifact))) (fatal :schema_invalid (str "missing sha256 for " coord ":" ver))
    (not (string? (:license artifact))) (fatal :schema_invalid (str "missing license for " coord ":" ver))
    (not (sequential? (:deps artifact))) (fatal :schema_invalid (str "deps must be vector for " coord ":" ver))
    (some (fn [{:keys [coord version scope optional]}]
            (or (not (version/valid-coord? coord))
                (not (valid-version-spec? version))
                (not (valid-scope? scope))
                (not (boolean? optional))))
          (:deps artifact))
    (fatal :schema_invalid (str "invalid dependency in " coord ":" ver))
    :else nil))

(defn- validate-versions [coord versions]
  (loop [vers (seq versions) seen #{}]
    (if (empty? vers)
      nil
      (let [[ver artifact] (first vers)]
        (or
         (when (contains? seen ver)
           (fatal :duplicate_primary_key (str "duplicate version " ver " for " coord)))
         (validate-artifact coord ver artifact)
         (recur (rest vers) (conj seen ver)))))))

(defn validate-repo [repo]
  (when (not (map? repo))
    (fatal :schema_invalid "local_repo.edn must be a map"))
  (loop [coords (seq repo)]
    (if (empty? coords)
      nil
      (let [[coord versions] (first coords)]
        (or
         (when (not (version/valid-coord? coord))
           (fatal :invalid_version (str "invalid repo coord " coord)))
         (when (not (map? versions))
           (fatal :schema_invalid (str "versions must be a map for " coord)))
         (validate-versions coord versions)
         (recur (rest coords)))))))

(defn validate-bom [bom]
  (when (not (map? bom))
    (fatal :schema_invalid "bom.edn must be a map"))
  (loop [[[coord spec] & entries] (seq bom)]
    (if (nil? coord)
      nil
      (or
       (when (not (version/valid-coord? coord))
         (fatal :invalid_version (str "invalid bom coord " coord)))
       (when (not (valid-version-spec? spec))
         (fatal :invalid_range (str "invalid bom entry for " coord)))
       (recur entries)))))

(defn validate-csv [csv expected-header label]
  (cond
    (nil? csv) (fatal :schema_invalid (str "missing " label))
    (not (header-valid? (:header csv) expected-header)) (fatal :schema_invalid (str "invalid " label " header"))
    :else nil))

(defn validate-relocations [csv]
  (or (validate-csv csv RELOCATION-HEADER "relocations.csv")
      (loop [rows (:rows csv) seen #{}]
        (if (empty? rows)
          nil
          (let [[from to _reason] (first rows)]
            (or
             (when (not (version/valid-coord? from))
               (fatal :schema_invalid "invalid relocation from_coord"))
             (when (not (version/valid-coord? to))
               (fatal :schema_invalid "invalid relocation to_coord"))
             (when (contains? seen from)
               (fatal :duplicate_primary_key (str "duplicate relocation from " from)))
             (recur (rest rows) (conj seen from))))))))

(defn validate-licenses [csv]
  (or (validate-csv csv LICENSES-HEADER "license_policy.csv")
      (when (not (every? (fn [[license status]]
                           (and (string? license) (contains? #{"allow" "warn" "deny"} status)))
                         (:rows csv)))
        (fatal :schema_invalid "invalid license policy row"))))

(defn load-bundle [data-dir]
  (try
    (let [config (read-config data-dir)
          roots (edn-io/read-edn-file (data-file data-dir "roots.edn"))
          repo (edn-io/read-edn-file (data-file data-dir "local_repo.edn"))
          bom (edn-io/read-edn-file (data-file data-dir "bom.edn"))
          relocations (read-optional-csv (data-file data-dir "relocations.csv") RELOCATION-HEADER)
          checksums (csv-io/read-csv-file (data-file data-dir "checksums.csv"))
          licenses (read-optional-csv (data-file data-dir "license_policy.csv") LICENSES-HEADER)
          bundle {:config config :roots roots :repo repo :bom bom
                  :relocations relocations :checksums checksums :licenses licenses}]
      (or (validate-config config)
          (validate-roots roots)
          (validate-repo repo)
          (validate-bom bom)
          (validate-relocations relocations)
          (validate-csv checksums CHECKSUMS-HEADER "checksums.csv")
          (validate-licenses licenses)
          (let [reloc-result (relocation/resolve-all-relocations (:rows relocations))]
            (or (when (:cycle? reloc-result)
                  (fatal :relocation_cycle "relocation cycle detected"))
                (let [relocated-repo (relocation/relocate-repo repo (:map reloc-result))
                      checksum-fatal (checksums/validate-checksum-rows
                                      relocated-repo (:rows checksums) (:map reloc-result))]
                  (or (when (:fatal? checksum-fatal)
                        (fatal (:reason checksum-fatal) (:detail checksum-fatal)))
                      {:ok (assoc bundle
                                  :relocated-repo relocated-repo
                                  :relocation-resolved (:map reloc-result)
                                  :relocation-result reloc-result)}))))))
    (catch Exception e
      (fatal :schema_invalid (.getMessage e)))))
