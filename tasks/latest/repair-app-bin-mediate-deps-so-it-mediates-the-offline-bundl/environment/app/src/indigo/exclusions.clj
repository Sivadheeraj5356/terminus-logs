(ns indigo.exclusions
  (:require [indigo.relocation :as relocation]))

(defn excluded? [coord exclusions]
  (contains? exclusions coord))

(defn relocate-exclusion-set [exclusions relocation-resolved]
  (into #{}
        (map (fn [coord]
               (:coord (relocation/relocate-coord coord relocation-resolved)))
             exclusions)))

(defn merge-exclusions [base additions relocation-resolved]
  (into (if (set? base) base (set base))
        (relocate-exclusion-set (or additions #{}) relocation-resolved)))
