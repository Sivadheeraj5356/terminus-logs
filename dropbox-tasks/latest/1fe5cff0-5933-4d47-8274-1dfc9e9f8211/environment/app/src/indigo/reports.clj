(ns indigo.reports
  (:require [clojure.string :as str]
            [indigo.csv-io :as csv-io]
            [indigo.models :as models]))

(defn reason-keyword->str [k]
  (name k))

(defn empty-by-reason []
  (into {}
        (map (fn [r] [(reason-keyword->str r) 0])
             (sort-by reason-keyword->str models/ALL-REASONS))))

(defn severity-rank [s]
  (case s
    :error 0
    :warning 1
    :critical 2
    3))

(defn sort-findings [findings]
  (sort-by (fn [f]
             [(severity-rank (:severity f))
              (if (str/blank? (:coord f)) 1 0)
              (or (:coord f) "zzzz")
              (if (str/blank? (:version f)) 1 0)
              (or (:version f) "zzzz")
              (name (:reason f))
              (:detail f)])
           findings))

(defn format-reason-codes [reasons]
  (if (empty? reasons)
    ""
    (str/join ";" (sort (map reason-keyword->str reasons)))))

(defn finding-rows [findings]
  (let [sorted (vec (sort-findings findings))]
    (map-indexed
     (fn [idx f]
       [(str "F" (format "%04d" (inc idx)))
        (reason-keyword->str (:reason f))
        (name (:severity f))
        (or (:coord f) "")
        (or (:version f) "")
        (:detail f)])
     sorted)))

(defn mediation-rows [selected]
  (->> (vals selected)
       (sort-by :coord)
       (map (fn [{:keys [coord requested version selected-by depth scope originals reasons]}]
              [coord
               (str/join ";" (sort requested))
               (or version "")
               (if selected-by (name selected-by) "")
               (str depth)
               (if scope (name scope) "")
               (str/join ";" (sort originals))
               (format-reason-codes reasons)]))))

(defn classpath-rows [classpath coord-reasons]
  (map-indexed
   (fn [idx {:keys [coord version scope jar sha256 license reasons]}]
     (let [all-reasons (into reasons (get coord-reasons coord #{}))]
       [(str "CP" (format "%04d" (inc idx)))
        coord
        (or version "")
        (if scope (name scope) "")
        (or jar "")
        (or sha256 "")
        (or license "")
        (format-reason-codes all-reasons)]))
   classpath))

(defn count-reason-codes [rows idx]
  (reduce (fn [m row]
            (let [codes (get row idx)]
              (if (str/blank? codes)
                m
                (reduce (fn [m2 code] (update m2 code (fnil inc 0)))
                        m
                        (str/split codes #";")))))
          {}
          rows))

(defn build-by-reason [findings mediation classpath-rows]
  (let [base (empty-by-reason)
        from-findings (reduce (fn [m f] (update m (reason-keyword->str (:reason f)) (fnil inc 0)))
                              {}
                              findings)
        from-med (count-reason-codes mediation 7)
        from-cp (count-reason-codes classpath-rows 7)]
    (merge-with +
                base
                from-findings
                from-med
                from-cp)))

(defn build-license-summary [selected classpath policy]
  (let [cp-coords (set (map :coord classpath))
        by-license
        (reduce-kv
         (fn [m coord {:keys [meta]}]
           (if-let [license (:license meta)]
             (update m license (fnil conj #{}) coord)
             m))
         {}
         selected)]
    (into {}
          (map (fn [[license coords]]
                 [license {:selected_count (count coords)
                           :classpath_count (count (filter cp-coords coords))
                           :status (name (or (get policy license) :unknown))}])
               (sort-by key by-license)))))

(defn json-escape [s]
  (-> s
      (str/replace "\\" "\\\\")
      (str/replace "\"" "\\\"")
      (str/replace "\n" "\\n")
      (str/replace "\r" "\\r")
      (str/replace "\t" "\\t")))

(defn json-str [s]
  (str "\"" (json-escape s) "\""))

(defn json-value [v indent]
  (cond
    (nil? v) "null"
    (boolean? v) (str v)
    (number? v) (str v)
    (string? v) (json-str v)
    (keyword? v) (json-str (name v))
    (map? v)
    (let [ks (keys v)
          ordered (vec (sort (fn [a b] (compare (str a) (str b))) ks))]
      (if (empty? ordered)
        "{}"
        (str "{\n"
             (str/join ",\n"
                        (map (fn [k]
                               (str (apply str (repeat indent "  ")) " "
                                    (json-str (name k)) ": "
                                    (json-value (get v k) (inc indent))))
                             ordered))
             "\n" (apply str (repeat indent " ")) "}")))

    (sequential? v)
    (if (empty? v)
      "[]"
      (str "[\n"
           (str/join ",\n"
                      (map (fn [item]
                             (str (apply str (repeat (inc indent) "  "))
                                  (json-value item (inc indent))))
                           v))
           "\n" (apply str (repeat indent " ")) "]"))

    :else (json-str (str v))))

(defn ordered-by-reason [counts]
  (into {}
        (map (fn [r] [(reason-keyword->str r) (get counts (reason-keyword->str r) 0)])
             (sort-by reason-keyword->str models/ALL-REASONS))))

(defn ordered-summary-json [summary]
  (str "{"
       "\"run_id\":" (json-value (:run_id summary) 0) ","
       "\"root_count\":" (json-value (:root_count summary) 0) ","
       "\"selected_count\":" (json-value (:selected_count summary) 0) ","
       "\"classpath_count\":" (json-value (:classpath_count summary) 0) ","
       "\"finding_count\":" (json-value (:finding_count summary) 0) ","
       "\"fatal\":" (json-value (:fatal summary) 0)
       "}"))

(defn- as-file [path]
  (if (instance? java.io.File path) path (java.io.File. (str path))))

(defn write-audit-json [path summary by-reason license-summary outputs]
  (let [file (as-file path)
        parent (.getParentFile file)]
    (when parent (.mkdirs parent))
    (spit file
          (str "{\n"
               "  \"summary\": " (ordered-summary-json summary) ",\n"
               "  \"by_reason\": " (json-value by-reason 1) ",\n"
               "  \"license_summary\": " (json-value license-summary 1) ",\n"
               "  \"outputs\": " (json-value outputs 1) "\n"
               "}"))))

(defn coord-reasons-from-findings [findings]
  (reduce (fn [m f]
            (if (str/blank? (:coord f))
              m
              (update m (:coord f) (fnil conj #{}) (:reason f))))
          {}
          findings))

(defn write-outputs! [result paths]
  (let [{:keys [selected classpath findings config]} result
        policy (:license-policy result)
        out-json (as-file (:out-json paths))
        out-cp (as-file (:out-classpath paths))
        out-med (as-file (:out-mediation paths))
        out-find (as-file (:out-findings paths))
        sorted-findings (vec (sort-findings findings))
        coord-reasons (coord-reasons-from-findings sorted-findings)
        classpath* (mapv (fn [row]
                           (update row :reasons
                                   (fn [rs]
                                     (into (or rs #{})
                                           (get coord-reasons (:coord row) #{})))))
                         classpath)
        med-rows (mediation-rows selected)
        cp-rows (classpath-rows classpath* coord-reasons)
        finding-rows* (finding-rows sorted-findings)
        summary {:run_id (:run-id config)
                 :root_count (count (:roots result))
                 :selected_count (count (filter #(not (str/blank? (nth % 2))) med-rows))
                 :classpath_count (count cp-rows)
                 :finding_count (count finding-rows*)
                 :fatal false}
        by-reason (ordered-by-reason (build-by-reason sorted-findings med-rows cp-rows))
        license-summary (build-license-summary selected classpath* policy)
        outputs {:classpath_csv (.getPath out-cp)
                 :mediation_csv (.getPath out-med)
                 :findings_csv (.getPath out-find)}]
    (when-let [parent (.getParentFile out-json)] (.mkdirs parent))
    (write-audit-json out-json summary by-reason license-summary outputs)
    (csv-io/write-csv-file out-cp
                           ["order" "coord" "version" "scope" "jar" "sha256" "license" "reason_codes"]
                           cp-rows)
    (csv-io/write-csv-file out-med
                           ["coord" "requested_versions" "selected_version" "selected_by" "depth" "scope" "original_coords" "reason_codes"]
                           med-rows)
    (csv-io/write-csv-file out-find
                           ["finding_id" "reason" "severity" "coord" "version" "detail"]
                           finding-rows*)))

(defn write-starter-outputs! [result paths]
  (write-outputs! result paths))
