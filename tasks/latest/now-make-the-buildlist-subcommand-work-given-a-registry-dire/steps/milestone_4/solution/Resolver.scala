package modverse

import java.nio.file.{Files, Path}

/** Result of a build list computation. */
final case class ResolveResult(
    buildList: Map[String, Version],
    loaded: List[String]
)

/** Computes a build list from a main module manifest against a registry. This
  * milestone adds the lang gated pruning of the walk. A manifest whose lang is at
  * or above the indirect tracking threshold records all of its requirements, so
  * the walk folds them into selection without descending into the dependency
  * manifests; a manifest below the threshold is walked over its full transitive
  * closure. The main module always opens its own direct requirements whatever its
  * lang. The build list is identical either way; the set of manifests read is not.
  */
final class Resolver(registry: Registry):
  private val pruneThreshold = LangVersion(1, 17)

  def resolve(mainPath: Path): ResolveResult =
    val main = registry.readManifestAt(mainPath, None)
    val mainReplaces = main.replaces
    val mainExcludes = main.excludes
    val mainDir = mainPath.toAbsolutePath.getParent

    def isExcluded(module: String, v: Version): Boolean =
      mainExcludes.exists(e =>
        e.path == module && VersionOrdering.compare(e.version, v) == 0
      )

    def excludedEffective(module: String, v: Version): Version =
      if !isExcluded(module, v) then v
      else
        val cands = registry
          .availableVersions(module)
          .filter(c => !isExcluded(module, c) && VersionOrdering.compare(c, v) >= 0)
        if cands.isEmpty then v
        else cands.reduce((a, b) => if VersionOrdering.compare(a, b) <= 0 then a else b)

    def replacementFor(module: String, v: Version): Option[Replace] =
      mainReplaces.foldLeft(Option.empty[Replace]) { (acc, r) =>
        if r.oldPath == module &&
          (r.oldVersion.isEmpty || VersionOrdering.compare(r.oldVersion.get, v) == 0)
        then Some(r)
        else acc
      }

    def manifestSource(
        module: String,
        v: Version
    ): (Option[Path], String, String, Version, Version) =
      replacementFor(module, v) match
        case None =>
          (None, registry.manifestRelPath(module, v), module, v, v)
        case Some(r) if r.newIsLocal =>
          val localFile = mainDir.resolve(r.newPath).normalize().resolve("module.mod")
          val recorded =
            if localFile.startsWith(registry.root) then
              registry.root.relativize(localFile).toString
            else r.newPath
          (Some(localFile), recorded, module, v, v)
        case Some(r) =>
          val nm = r.newPath
          val nv = r.newVersion.get
          (None, registry.manifestRelPath(nm, nv), nm, nv, nv)

    val requiredMax = scala.collection.mutable.LinkedHashMap.empty[String, Version]
    val queued = scala.collection.mutable.HashSet.empty[(String, String)]
    val work = scala.collection.mutable.Stack.empty[(String, Version)]

    def bump(module: String, v: Version): Unit =
      val ev = excludedEffective(module, v)
      requiredMax.get(module) match
        case Some(cur) if VersionOrdering.compare(ev, cur) <= 0 => ()
        case _ => requiredMax(module) = ev

    def enqueue(module: String, v: Version): Unit =
      val ev = excludedEffective(module, v)
      val key = (module, ev.raw)
      if !queued.contains(key) then
        queued += key
        work.push((module, ev))

    for r <- main.requires do
      bump(r.path, r.version)
      enqueue(r.path, r.version)

    while work.nonEmpty do
      val (module, v) = work.pop()
      val (localOpt, recorded, regModule, regVersion, _) = manifestSource(module, v)
      val manOpt = localOpt match
        case Some(p) =>
          if Files.isRegularFile(p) then Some(registry.readManifestAt(p, Some(recorded)))
          else None
        case None =>
          if registry.has(regModule, regVersion) then
            Some(registry.readManifestRel(recorded))
          else None
      manOpt.foreach { man =>
        val pruned = man.lang >= pruneThreshold
        for req <- man.requires do
          bump(req.path, req.version)
          if !pruned then enqueue(req.path, req.version)
      }

    val selected = requiredMax.toList.map { case (module, v) =>
      val (_, _, _, _, eff) = manifestSource(module, v)
      module -> eff
    }.toMap

    ResolveResult(selected, registry.loaded)
