(ns indigo.graph
  (:require [clojure.string :as str]
            [indigo.bom :as bom]
            [indigo.checksums :as checksums]
            [indigo.exclusions :as exclusions]
            [indigo.licenses :as licenses]
            [indigo.ranges :as ranges]
            [indigo.relocation :as relocation]
            [indigo.version :as version]))

(defn scope-rank [scope-order scope]
  (or (.indexOf scope-order scope) Integer/MAX_VALUE))

(defn pick-scope [scope-order requests]
  (when (seq requests)
    (:scope (first (sort-by #(scope-rank scope-order (:scope %)) requests)))))

(defn parse-version-spec [s]
  (or (ranges/parse-range s) (throw (ex-info "invalid range" {:spec s}))))

(defn available-versions [repo coord]
  (vec (keys (get repo coord))))

(defn select-root-version [coord version-spec repo bom]
  (let [parsed (parse-version-spec version-spec)
        candidates (available-versions repo coord)
        picked (if (= :exact (:kind parsed))
                 (:version parsed)
                 (version/highest-version (ranges/versions-in-range candidates parsed)))]
    (when-not picked
      (throw (ex-info "unresolved root" {:coord coord})))
    (if-let [bom-entry (get bom coord)]
      (let [{:keys [version selected-by reasons]}
            (bom/apply-bom coord [parsed] bom-entry candidates)]
        (if version
          {:version version :selected-by (if (= selected-by :bom) :root selected-by) :reasons reasons}
          {:version picked :selected-by :root :reasons reasons}))
      {:version picked :selected-by :root :reasons #{}})))

(defn mediate-coord [coord requests repo bom root?]
  (let [min-depth (apply min (map :depth requests))
        nearest (filter #(= min-depth (:depth %)) requests)
        nearest-ranges (mapv #(parse-version-spec (:version %)) nearest)
        candidates (available-versions repo coord)
        bom-entry (get bom coord)
        {:keys [version selected-by reasons]}
        (if root?
          (let [parsed (first nearest-ranges)
                picked (if (= :exact (:kind parsed))
                         (:version parsed)
                         (version/highest-version
                          (ranges/versions-in-range candidates parsed)))]
            {:version picked :selected-by :root :reasons #{}})
          (bom/apply-bom coord nearest-ranges bom-entry candidates))
        requested (into #{} (map :version requests))
        originals (into #{} (mapcat :originals requests))]
    {:coord coord
     :version version
     :depth min-depth
     :selected-by selected-by
     :requested requested
     :originals originals
     :reasons (set reasons)}))

(defn relocate-dep [dep relocation-resolved]
  (let [orig (:coord dep)
        {:keys [coord originals]} (relocation/relocate-coord orig relocation-resolved)]
    (assoc dep :coord coord :originals (set originals) :original-coord orig)))

(defn root-coords [roots]
  (set (map :coord roots)))

(defn collect-requests [roots selected repo config relocation-resolved]
  (let [optional-default (:optional-default config)
        roots-set (root-coords roots)
        root-requests
        (reduce (fn [m root]
                  (let [{:keys [coord originals]} (relocation/relocate-coord (:coord root) relocation-resolved)]
                    (update m coord (fnil conj [])
                            {:depth 1
                             :version (:version root)
                             :scope (:scope root)
                             :originals originals
                             :optional false})))
                {}
                roots)
        expand-deps
        (fn expand-deps [deps queue requests depth exclusions]
          (if (empty? deps)
            [queue requests]
            (let [dep (relocate-dep (first deps) relocation-resolved)
                  dep-coord (:coord dep)
                  excl (exclusions/merge-exclusions exclusions (:exclusions dep) relocation-resolved)
                  optional? (:optional dep)
                  skip? (or (and optional? (not optional-default) (not (contains? roots-set dep-coord)))
                            (exclusions/excluded? dep-coord excl))]
              (if skip?
                (expand-deps (rest deps) queue requests depth exclusions)
                (let [req {:depth depth
                           :version (:version dep)
                           :scope (:scope dep)
                           :originals (:originals dep)
                           :optional optional?}
                      reqs' (update requests dep-coord (fnil conj []) req)
                      q' (conj queue {:coord dep-coord :depth depth :exclusions excl})
                      sel-dep (get selected dep-coord)
                      queue'
                      (if (and sel-dep (get-in repo [dep-coord (:version sel-dep)]))
                        q'
                        queue)]
                  (expand-deps (rest deps) queue' reqs' depth exclusions))))))]
    (loop [queue (vec (for [root roots
                             :let [{:keys [coord]} (relocation/relocate-coord (:coord root) relocation-resolved)
                                   sel (get selected coord)]
                             :when sel]
                         {:coord coord :depth 1 :exclusions (exclusions/relocate-exclusion-set (set (:exclusions root)) relocation-resolved)}))
           requests root-requests]
      (if (empty? queue)
        requests
        (let [{:keys [coord depth exclusions]} (first queue)
              entry (get selected coord)
              version (:version entry)
              artifact (get-in repo [coord version])
              next-depth (inc depth)
              [q' reqs'] (if (nil? artifact)
                           [(rest queue) requests]
                           (expand-deps (:deps artifact) (rest queue) requests next-depth exclusions))]
          (recur q' reqs'))))))

(defn mediate-all [requests repo bom roots]
  (let [root-set (root-coords roots)]
    (into {}
          (map (fn [[coord reqs]]
                 [coord (mediate-coord coord reqs repo bom (contains? root-set coord))])
               requests))))

(defn fixpoint-selected [roots repo bom config relocation-resolved]
  (let [initial-roots
        (into {}
              (map (fn [root]
                     (let [{:keys [coord]} (relocation/relocate-coord (:coord root) relocation-resolved)
                           {:keys [version selected-by reasons]}
                           (select-root-version coord (:version root) repo bom)]
                       [coord {:version version :selected-by selected-by :reasons reasons}]))
                   roots))]
    (loop [selected initial-roots
           iterations 0]
      (let [requests (collect-requests roots selected repo config relocation-resolved)
            mediated (mediate-all requests repo bom roots)
            new-selected
            (into {}
                  (map (fn [[coord m]]
                         [coord {:version (:version m)
                                 :selected-by (:selected-by m)
                                 :reasons (:reasons m)}])
                       mediated))]
        (if (or (= selected new-selected) (> iterations 20))
          [requests mediated new-selected]
          (recur (merge selected new-selected) (inc iterations)))))))

(defn build-selected-details [requests mediated repo config]
  (let [scope-order (:scope-order config)]
    (into {}
          (map (fn [[coord m]]
                 (let [reqs (get requests coord [])
                       artifact (when (:version m) (get-in repo [coord (:version m)]))]
                   [coord (assoc m
                                 :coord coord
                                 :depth (apply min (map :depth reqs))
                                 :scope (pick-scope scope-order reqs)
                                 :requested (into #{} (map :version reqs))
                                 :originals (into #{} (mapcat :originals reqs))
                                 :meta artifact)]))
               mediated))))

(defn detect-cycle [selected repo]
  (let [nodes (set (keys selected))
        edges (reduce-kv
               (fn [m coord {:keys [version]}]
                 (let [deps (:deps (get-in repo [coord version]))]
                   (assoc m coord
                          (into #{}
                                (keep (fn [{:keys [coord]}]
                                        (when (contains? nodes coord) coord))
                                      deps)))))
               {}
               selected)]
    (loop [stack []
           visited #{}
           active #{}
           [node & more] (sort nodes)]
      (cond
        (nil? node) false
        (contains? active node) true
        (contains? visited node) (recur stack visited active more)
        :else
        (let [dfs (fn dfs [n vis act]
                    (if (contains? act n)
                      true
                      (if (contains? vis n)
                        false
                        (let [vis' (conj vis n)
                              act' (conj act n)]
                          (if (some #(dfs % vis' act') (get edges n))
                            true
                            false)))))]
          (if (dfs node #{} #{})
            true
            (recur stack (conj visited node) active more)))))))

(defn classpath-comparator [scope-order]
  (fn [a b]
    (let [cmp (compare (:depth a) (:depth b))]
      (if (not= 0 cmp) cmp
          (let [cmp2 (compare (scope-rank scope-order (:scope a))
                              (scope-rank scope-order (:scope b)))]
            (if (not= 0 cmp2) cmp2
                (let [cmp3 (compare (:coord a) (:coord b))]
                  (if (not= 0 cmp3) cmp3
                      (version/compare-versions (:version a) (:version b))))))))))

(defn topological-classpath [selected repo config relocation-resolved]
  (let [scope-order (:scope-order config)
        include-scopes (:include-scopes config)
        nodes (into {}
                    (keep (fn [[coord entry]]
                            (when (contains? include-scopes (:scope entry))
                              [coord entry]))
                          (sort-by key selected)))
        node-set (set (keys nodes))
        resolve-dep-coord
        (fn [dep]
          (:coord (relocation/relocate-coord (:coord dep) relocation-resolved)))
        dep-count
        (fn [coord]
          (let [{:keys [version]} (get nodes coord)
                artifact (get-in repo [coord version])]
            (count (keep (fn [dep]
                           (let [dep-coord (resolve-dep-coord dep)]
                             (when (contains? node-set dep-coord) dep-coord)))
                         (:deps artifact)))))
        in-degree (into {} (map (fn [coord] [coord (dep-count coord)]) node-set))
        dependents (reduce-kv
                    (fn [m parent-coord {:keys [version]}]
                      (let [deps (:deps (get-in repo [parent-coord version]))]
                        (reduce (fn [m2 dep]
                                  (let [dep-coord (resolve-dep-coord dep)]
                                    (if (contains? node-set dep-coord)
                                      (update m2 dep-coord (fnil conj []) parent-coord)
                                      m2)))
                                m
                                deps)))
                    {}
                    nodes)
        cmp (classpath-comparator scope-order)
        ready (fn [deg nodes-left]
                (vec (sort cmp (map (fn [c] (assoc (get nodes c) :coord c))
                                    (filter #(zero? (get deg % 0)) nodes-left)))))
        node->entry nodes]
    (loop [deg in-degree
           remaining node-set
           order []]
      (if (empty? remaining)
        (mapv (fn [coord]
                (let [entry (get node->entry coord)
                      artifact (:meta entry)]
                  {:coord coord
                   :version (:version entry)
                   :scope (:scope entry)
                   :depth (:depth entry)
                   :jar (:jar artifact)
                   :sha256 (:sha256 artifact)
                   :license (:license artifact)
                   :reasons (:reasons entry)}))
              order)
        (let [candidates (ready deg remaining)]
          (if (empty? candidates)
            nil
            (let [pick (:coord (first candidates))
                  deg' (reduce (fn [d dep] (update d dep dec))
                               deg
                               (get dependents pick []))
                  remaining' (disj remaining pick)]
              (recur deg' remaining' (conj order pick)))))))))

(defn scope-excluded-findings [selected config]
  (let [include-scopes (:include-scopes config)]
    (for [[coord entry] selected
          :when (not (contains? include-scopes (:scope entry)))]
      {:reason :scope_excluded
       :severity :warning
       :coord coord
       :version (:version entry)
       :detail (str "scope " (:scope entry) " excluded from classpath")})))

(defn range-conflict-findings [mediated repo]
  (for [[coord m] mediated
        :when (and (nil? (:version m))
                   (contains? (:reasons m) :range_conflict))]
    {:reason :range_conflict
     :severity :error
     :coord coord
     :version ""
     :detail "no version satisfies range intersection"}))

(defn bom-rejected-findings [mediated]
  (for [[coord m] mediated
        :when (contains? (:reasons m) :bom_override_rejected)]
    {:reason :bom_override_rejected
     :severity :warning
     :coord coord
     :version (:version m)
     :detail "bom version outside dependency range"}))

(defn relocated-findings [relocation-rows relocation-resolved]
  (for [row relocation-rows
        :let [[from _to reason] row
              {:keys [coord originals relocated?]} (relocation/relocate-coord from relocation-resolved)]
        :when relocated?]
    {:reason :relocated_artifact
     :severity :warning
     :coord coord
     :version ""
     :detail (str (str/join "->" originals) " " reason)}))

(defn mediate [bundle]
  (let [{:keys [config roots relocated-repo bom relocations checksums licenses
                relocation-resolved relocation-result]} bundle
        checksum-map (checksums/build-checksum-map (:rows checksums) relocation-resolved)
        policy (licenses/build-policy-map (:rows licenses))
        [requests mediated raw-selected]
        (fixpoint-selected roots relocated-repo bom config relocation-resolved)
        unresolved (filter #(let [m (val %)
                                  coord (key %)]
                              (and (nil? (:version m))
                                   (or (not (contains? relocated-repo coord))
                                       (not (contains? (:reasons m) :range_conflict)))))
                         mediated)
        _ (when (seq unresolved)
            (throw (ex-info "unresolved" {:reason :unresolved_required_artifact
                                          :coord (first (keys unresolved))})))
        selected (build-selected-details requests mediated relocated-repo config)
        _ (when (and (= :fatal (:cycle-mode config)) (detect-cycle selected relocated-repo))
            (throw (ex-info "cycle" {:reason :dependency_cycle})))
        raw-classpath (or (topological-classpath selected relocated-repo config relocation-resolved)
                          (throw (ex-info "classpath cycle" {:reason :dependency_cycle})))
        classpath (mapv (fn [row]
                          (let [sel (get selected (:coord row))]
                            (assoc row :reasons (:reasons sel))))
                        raw-classpath)
        checksum-findings
        (mapcat (fn [{:keys [coord version sha256]}]
                  (or (checksums/check-artifact coord version sha256 checksum-map
                                                (:checksum-mode config))
                      []))
                classpath)
        license-findings
        (mapcat (fn [coord]
                  (let [{:keys [version meta]} (get selected coord)]
                    (licenses/license-findings coord version (:license meta) policy)))
                (sort (keys selected)))
        findings (vec (concat (relocated-findings (:rows relocations) relocation-resolved)
                              (bom-rejected-findings mediated)
                              (range-conflict-findings mediated relocated-repo)
                              (scope-excluded-findings selected config)
                              checksum-findings
                              license-findings))
        fatal-checksum? (and (= :fatal (:checksum-mode config))
                             (some #(= :critical (:severity %)) checksum-findings))]
    (when fatal-checksum?
      (throw (ex-info "checksum fatal" {:reason :checksum_mismatch})))
    {:selected selected
     :classpath classpath
     :findings findings
     :config config
     :roots roots
     :requests requests
     :relocated-repo relocated-repo}))

(defn mediate-direct-only [bundle]
  (mediate bundle))
