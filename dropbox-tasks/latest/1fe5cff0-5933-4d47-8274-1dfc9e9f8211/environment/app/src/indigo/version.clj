(ns indigo.version
  (:require [clojure.string :as str]))

(defn valid-coord? [s]
  (boolean (and (string? s) (re-matches #"[^:\s]+:[^:\s]+" s))))

(defn parse-version [s]
  (when (string? s)
    (let [[base qualifier] (str/split s #"-" 2)
          parts (str/split base #"\.")]
      (when (= 3 (count parts))
        (try
          {:major (Long/parseLong (nth parts 0))
           :minor (Long/parseLong (nth parts 1))
           :patch (Long/parseLong (nth parts 2))
           :qualifier qualifier
           :raw s}
          (catch NumberFormatException _ nil))))))

(defn valid-version? [s]
  (boolean (parse-version s)))

(defn compare-versions [a b]
  (let [va (if (string? a) (parse-version a) a)
        vb (if (string? b) (parse-version b) b)]
    (cond
      (nil? va) 1
      (nil? vb) -1
      :else (let [c (compare (:major va) (:major vb))]
              (if (not= 0 c) c
                  (let [c2 (compare (:minor va) (:minor vb))]
                    (if (not= 0 c2) c2
                        (let [c3 (compare (:patch va) (:patch vb))]
                          (if (not= 0 c3) c3
                              (cond
                                (and (nil? (:qualifier va)) (nil? (:qualifier vb))) 0
                                (nil? (:qualifier va)) 1
                                (nil? (:qualifier vb)) -1
                                :else (compare (:qualifier va) (:qualifier vb))))))))))))

(defn highest-version [versions]
  (first (sort (fn [a b] (compare-versions b a)) versions)))
