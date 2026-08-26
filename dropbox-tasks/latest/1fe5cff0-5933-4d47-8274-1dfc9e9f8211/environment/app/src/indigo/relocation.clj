(ns indigo.relocation
  (:require [clojure.string :as str]
            [indigo.version :as version]))

(defn build-relocation-map [rows]
  (reduce (fn [m row]
            (let [[from to _reason] row]
              (assoc m from to)))
          {}
          rows))

(defn- follow-chain [coord relocation-map visited]
  (loop [current coord
         originals [coord]
         seen #{}]
    (if (contains? seen current)
      {:coord current :originals originals :cycle? true}
      (if-let [next (get relocation-map current)]
        (recur next (conj originals next) (conj seen current))
        {:coord current :originals originals :cycle? false}))))

(defn resolve-all-relocations [relocation-rows]
  (let [relocation-map (build-relocation-map relocation-rows)
        from-coords (set (keys relocation-map))]
    (loop [coords (seq from-coords)
           resolved {}
           cycle? false]
      (if (empty? coords)
        {:map resolved :cycle? cycle? :relocation-map relocation-map}
        (let [from (first coords)
              {:keys [coord originals cycle?]} (follow-chain from relocation-map #{})]
          (if cycle?
            {:map resolved :cycle? true :relocation-map relocation-map}
            (recur (rest coords)
                   (reduce (fn [m orig] (assoc m orig {:coord coord :originals originals}))
                           resolved
                           originals)
                   cycle?)))))))

(defn relocate-coord [coord relocation-resolved]
  (if-let [{:keys [coord originals]} (get relocation-resolved coord)]
    {:coord coord :originals (vec originals) :relocated? (not= (first originals) coord)}
    {:coord coord :originals [coord] :relocated? false}))

(defn relocate-repo [repo relocation-resolved]
  (reduce-kv
   (fn [m coord versions]
     (let [{:keys [coord new-coord]} (let [r (relocate-coord coord relocation-resolved)]
                                       {:coord (:coord r) :new-coord (:coord r)})
           target (or new-coord coord)]
       (update m target merge versions)))
   {}
   repo))

(defn relocation-findings [relocation-rows relocation-resolved]
  (for [row relocation-rows
        :let [[from to reason] row
              {:keys [coord originals relocated?]} (relocate-coord from relocation-resolved)]
        :when relocated?]
    {:reason :relocated_artifact
     :coord coord
     :version ""
     :detail (str "relocated " (str/join "->" originals) " reason=" reason)}))
