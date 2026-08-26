(ns indigo.checksums
  (:require [indigo.version :as version]))

(defn validate-checksum-rows [repo rows relocation-resolved]
  (let [relocate (fn [coord]
                   (if-let [entry (get relocation-resolved coord)]
                     (:coord entry)
                     coord))]
    (loop [rows rows
           seen #{}
           dup? false
           unknown nil]
      (if (empty? rows)
        (cond
          dup? {:fatal? true :reason :duplicate_primary_key
                :detail "duplicate checksum coord:version"}
          unknown {:fatal? true :reason :unknown_checksum_row :detail unknown}
          :else {:fatal? false :map {}})
        (let [[coord ver sha] (first rows)
              key [coord ver]
              relocated (relocate coord)]
          (cond
            (contains? seen key)
            {:fatal? true :reason :duplicate_primary_key
             :detail "duplicate checksum coord:version"}

            (or (not (version/valid-coord? coord))
                (not (version/valid-version? ver)))
            {:fatal? true :reason :schema_invalid :detail "invalid checksum row"}

            (nil? (get-in repo [relocated ver]))
            {:fatal? true :reason :unknown_checksum_row
             :detail (str relocated ":" ver)}

            :else
            (recur (rest rows)
                   (conj seen key)
                   false
                   nil)))))))

(defn build-checksum-map [rows relocation-resolved]
  (let [relocate (fn [coord]
                   (if-let [entry (get relocation-resolved coord)]
                     (:coord entry)
                     coord))]
    (into {}
          (map (fn [[coord ver sha]]
                 [[(relocate coord) ver] sha])
               rows))))

(defn check-artifact [coord version repo-sha checksum-map mode]
  (when-let [expected (get checksum-map [coord version])]
    (when (and repo-sha (not= expected repo-sha))
      (let [severity (if (= mode :fatal) :critical :warning)]
        [{:reason :checksum_mismatch
          :severity severity
          :coord coord
          :version version
          :detail (str "expected " expected " got " repo-sha)}]))))
