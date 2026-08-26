(ns indigo.bom
  (:require [indigo.ranges :as ranges]
            [indigo.version :as version]))

(defn- intersect-requests [requested-ranges]
  (reduce (fn [acc r] (if acc (ranges/intersect-ranges acc r) r))
          nil
          requested-ranges))

(defn- pick-highest [candidates range]
  (version/highest-version (ranges/versions-in-range candidates range)))

(defn- pick-nearest-version [nearest-ranges candidates]
  (if (every? #(= :exact (:kind %)) nearest-ranges)
    (let [requested (map :version nearest-ranges)
          available (filter #(some (partial = %) requested) candidates)]
      (version/highest-version available))
    (let [intersected (intersect-requests nearest-ranges)]
      (when intersected (pick-highest candidates intersected)))))

(defn apply-bom [_coord requested-ranges bom-entry candidates]
  (let [in-range? (fn [v] (some #(ranges/version-in-range? % v) requested-ranges))
        candidates-in-intersection (vec (filter in-range? candidates))]
    (cond
      (nil? (intersect-requests requested-ranges))
      (if (every? #(= :exact (:kind %)) requested-ranges)
        (let [picked (pick-nearest-version requested-ranges candidates)]
          {:version picked
           :selected-by (if picked :highest :nearest)
           :reasons (if picked #{} #{:range_conflict})})
        {:version nil :selected-by :nearest :reasons #{:range_conflict}})

      (nil? bom-entry)
      (let [picked (or (pick-nearest-version requested-ranges candidates)
                        (pick-highest candidates (intersect-requests requested-ranges)))]
        {:version picked
         :selected-by (if picked :nearest :highest)
         :reasons (if picked #{} #{:range_conflict})})

      :else
      (let [bom-range (ranges/parse-range bom-entry)]
        (cond
          (nil? bom-range)
          (let [picked (or (pick-nearest-version requested-ranges candidates)
                            (pick-highest candidates (intersect-requests requested-ranges)))]
            {:version picked
             :selected-by (if picked :nearest :highest)
             :reasons (if picked #{} #{:range_conflict})})

          (= :exact (:kind bom-range))
          (let [bom-ver (:version bom-range)]
            (if (in-range? bom-ver)
              {:version bom-ver :selected-by :bom :reasons #{}}
              (let [fallback (version/highest-version candidates-in-intersection)]
                {:version fallback
                 :selected-by (if fallback :highest :nearest)
                 :reasons #{:bom_override_rejected}})))

          :else
          (let [final-range (ranges/intersect-ranges (intersect-requests requested-ranges) bom-range)
                picked (or (when final-range (pick-highest candidates final-range))
                           (pick-nearest-version requested-ranges candidates))]
            (if picked
              {:version picked :selected-by :bom :reasons #{}}
              {:version nil :selected-by :nearest :reasons #{:range_conflict}})))))))
