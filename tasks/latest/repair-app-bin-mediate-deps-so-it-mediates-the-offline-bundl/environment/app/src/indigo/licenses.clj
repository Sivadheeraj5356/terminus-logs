(ns indigo.licenses)

(defn build-policy-map [rows]
  (into {} (map (fn [[license status]] [license (keyword status)]) rows)))

(defn license-status [license policy]
  (or (get policy license) :unknown))

(defn license-findings [coord version license policy]
  (case (license-status license policy)
    :deny [{:reason :license_denied :severity :error
            :coord coord :version version
            :detail (str "license " license " denied")}]
    :warn [{:reason :license_unknown :severity :warning
            :coord coord :version version
            :detail (str "license " license " warn")}]
    :allow []
    [{:reason :license_unknown :severity :warning
      :coord coord :version version
      :detail (str "license " license " unknown")}]))
