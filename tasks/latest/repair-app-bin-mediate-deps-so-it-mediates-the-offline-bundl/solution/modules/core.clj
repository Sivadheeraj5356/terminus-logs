(ns indigo.core
  (:require [indigo.graph :as graph]
            [indigo.loader :as loader]
            [indigo.licenses :as licenses]
            [indigo.reports :as reports]))

(defn fatal-exit-code [{:keys [fatal]}]
  (println (str (name fatal)))
  1)

(defn run-mediation! [data-dir paths]
  (let [loaded (loader/load-bundle data-dir)]
    (if (:fatal loaded)
      (fatal-exit-code loaded)
      (try
        (let [bundle (:ok loaded)
              policy (licenses/build-policy-map (:rows (:licenses bundle)))
              result (graph/mediate bundle)]
          (reports/write-outputs! (assoc result :license-policy policy) paths)
          0)
        (catch clojure.lang.ExceptionInfo e
          (let [reason (get-in (ex-data e) [:reason] :schema_invalid)]
            (println (name reason))
            1))))))
