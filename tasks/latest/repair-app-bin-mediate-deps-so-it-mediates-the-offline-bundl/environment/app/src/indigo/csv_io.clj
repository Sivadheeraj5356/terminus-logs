(ns indigo.csv-io
  (:require [clojure.data.csv :as csv]
            [clojure.java.io :as io]))

(defn read-csv-file [path]
  (with-open [r (io/reader path)]
    (let [rows (vec (csv/read-csv r))]
      {:header (first rows) :rows (vec (rest rows))})))

(defn write-csv-file [path header rows]
  (.mkdirs (.getParentFile (io/file path)))
  (with-open [w (io/writer path)]
    (csv/write-csv w (cons header rows))))
