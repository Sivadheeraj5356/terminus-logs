package modverse

import java.nio.file.Path

/** Result of a build list computation. buildList maps each selected module to
  * its selected version. loaded is the registry relative paths of the manifests
  * read while computing it, excluding the main module manifest.
  */
final case class ResolveResult(
    buildList: Map[String, Version],
    loaded: List[String]
)

/** Computes a build list from a main module manifest against a registry. The
  * result is the build list and the set of loaded manifests, in the JSON shape
  * fixed by /app/app/docs/CLI.md.
  */
final class Resolver(registry: Registry):

  /** Compute the build list and the set of loaded manifests for the main module
    * whose manifest is at mainPath.
    */
  def resolve(mainPath: Path): ResolveResult =
    throw new NotImplementedError(
      "build list resolution is not implemented yet"
    )
