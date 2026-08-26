(ns indigo.edn-io
  (:require [clojure.edn :as edn]
            [clojure.java.io :as io]))

(defn read-edn-file [path]
  (with-open [r (java.io.PushbackReader. (io/reader path))]
    (edn/read {:eof nil} r)))
