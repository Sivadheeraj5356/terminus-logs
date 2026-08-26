(ns indigo.ranges
  (:require [indigo.version :as version]))

(defn parse-range [s]
  (cond
    (version/valid-version? s)
    {:kind :exact :version s}

    (and (string? s) (re-matches #"\[[^\],]+\]" s))
    (let [inner (-> s subs 1 dec)]
      (when (version/valid-version? inner)
        {:kind :exact :version inner}))

    (and (string? s) (re-matches #"\[[^,\]]+,[^,\]]+\)" s))
    (let [[_ lower upper] (re-matches #"\[([^,\]]+),([^\]]+)\)" s)]
      (when (and (version/valid-version? lower) (version/valid-version? upper))
        {:kind :bounded :lower lower :upper upper
         :lower-inclusive? true :upper-inclusive? false}))

    (and (string? s) (re-matches #"\([^,\]]+,[^\]]+\]" s))
    (let [[_ lower upper] (re-matches #"\(([^,\]]+),([^\]]+)\]" s)]
      (when (and (version/valid-version? lower) (version/valid-version? upper))
        {:kind :bounded :lower lower :upper upper
         :lower-inclusive? false :upper-inclusive? true}))

    :else nil))

(defn- lower-bound-ok? [range v]
  (let [cmp (version/compare-versions v (:lower range))]
    (if (:lower-inclusive? range) (not (neg? cmp)) (pos? cmp))))

(defn- upper-bound-ok? [range v]
  (let [cmp (version/compare-versions v (:upper range))]
    (if (:upper-inclusive? range) (not (pos? cmp)) (neg? cmp))))

(defn version-in-range? [range v]
  (cond
    (nil? range) false
    (= :exact (:kind range)) (= v (:version range))
    (= :bounded (:kind range))
    (and (lower-bound-ok? range v) (upper-bound-ok? range v))
    :else false))

(defn intersect-ranges [a b]
  (cond
    (nil? a) nil
    (nil? b) nil
    (= :exact (:kind a)) (when (version-in-range? b (:version a)) a)
    (= :exact (:kind b)) (when (version-in-range? a (:version b)) b)
    :else
    (let [lower (if (pos? (version/compare-versions (:lower a) (:lower b)))
                  (:lower a) (:lower b))
          lower-inc? (if (= lower (:lower a)) (:lower-inclusive? a) (:lower-inclusive? b))
          upper (if (neg? (version/compare-versions (:upper a) (:upper b)))
                  (:upper a) (:upper b))
          upper-inc? (if (= upper (:upper a)) (:upper-inclusive? a) (:upper-inclusive? b))
          candidate {:kind :bounded :lower lower :upper upper
                     :lower-inclusive? lower-inc? :upper-inclusive? upper-inc?}]
      (when (or (version/compare-versions lower upper)
                 (and (= 0 (version/compare-versions lower upper))
                      (or lower-inc? upper-inc?)))
        candidate))))

(defn versions-in-range [versions range]
  (vec (filter #(version-in-range? range %) versions)))
