package modverse

import java.nio.file.{Files, Path}

/** Result of a build list computation. */
final case class ResolveResult(
    buildList: Map[String, Version],
    loaded: List[String]
)

/** Computes a build list from a main module manifest against a registry. This
  * milestone implements the core selection rule and the lazy transitive walk.
  * The selected version of each module is the maximum of every version required
  * of it across the graph, every required module version's manifest is read when
  * reached, and the main module is not part of the list.
  */
final class Resolver(registry: Registry):

  def resolve(mainPath: Path): ResolveResult =
    val main = registry.readManifestAt(mainPath, None)

    val requiredMax = scala.collection.mutable.LinkedHashMap.empty[String, Version]
    val queued = scala.collection.mutable.HashSet.empty[(String, String)]
    val work = scala.collection.mutable.Stack.empty[(String, Version)]

    def bump(module: String, v: Version): Unit =
      requiredMax.get(module) match
        case Some(cur) if VersionOrdering.compare(v, cur) <= 0 => ()
        case _ => requiredMax(module) = v

    def enqueue(module: String, v: Version): Unit =
      val key = (module, v.raw)
      if !queued.contains(key) then
        queued += key
        work.push((module, v))

    for r <- main.requires do
      bump(r.path, r.version)
      enqueue(r.path, r.version)

    while work.nonEmpty do
      val (module, v) = work.pop()
      if registry.has(module, v) then
        val man = registry.readManifestRel(registry.manifestRelPath(module, v))
        for req <- man.requires do
          bump(req.path, req.version)
          enqueue(req.path, req.version)

    ResolveResult(requiredMax.toMap, registry.loaded)
