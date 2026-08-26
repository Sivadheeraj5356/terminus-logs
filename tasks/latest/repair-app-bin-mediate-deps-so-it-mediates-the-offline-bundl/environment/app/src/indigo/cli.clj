(ns indigo.cli
  (:require [clojure.string :as str]
            [indigo.core :as core])
  (:gen-class))

(def REQUIRED-FLAGS
  #{:data-dir :out-json :out-classpath :out-mediation :out-findings})

(defn parse-args [args]
  (loop [remaining args
         opts {}]
    (if (empty? remaining)
      opts
      (let [arg (first remaining)]
        (cond
          (str/starts-with? arg "--")
          (let [k (keyword (subs arg 2))
                v (second remaining)]
            (when (nil? v)
              (throw (ex-info "missing flag value" {:flag arg})))
            (recur (drop 2 remaining) (assoc opts k v)))
          :else
          (throw (ex-info "positional arguments not allowed" {:arg arg})))))))

(defn -main [& args]
  (try
    (when (empty? args)
      (throw (ex-info "missing required flags" {})))
    (let [opts (parse-args args)
          extra (remove REQUIRED-FLAGS (keys opts))
          missing (remove #(contains? opts %) REQUIRED-FLAGS)]
      (when (seq extra)
        (throw (ex-info "unknown flags" {:extra extra})))
      (when (seq missing)
        (throw (ex-info "missing required flags" {:missing missing})))
      (let [paths {:data-dir (:data-dir opts)
                   :out-json (java.io.File. (:out-json opts))
                   :out-classpath (java.io.File. (:out-classpath opts))
                   :out-mediation (java.io.File. (:out-mediation opts))
                   :out-findings (java.io.File. (:out-findings opts))}]
        (System/exit (core/run-mediation! (:data-dir paths) paths))))
    (catch Exception e
      (println (.getMessage e))
      (System/exit 1))))
