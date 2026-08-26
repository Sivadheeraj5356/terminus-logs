package modverse

import java.nio.file.{Files, Path, Paths}
import scala.jdk.CollectionConverters.*

/** A registry is a directory tree of module manifests. The manifest for module
  * `a/b` at version `v1.2.0` lives at `a/b@v1.2.0/module.mod` beneath the root.
  * This layer only locates and reads manifest bytes and tracks the registry
  * relative paths it has read; it does not interpret the build rules.
  */
final class Registry(val root: Path):
  private val loadedPaths = scala.collection.mutable.LinkedHashSet.empty[String]

  /** Registry relative path of a module version's manifest. */
  def manifestRelPath(module: String, version: Version): String =
    s"$module@${version.display}/module.mod"

  /** Absolute path of a module version's manifest. */
  def manifestPath(module: String, version: Version): Path =
    root.resolve(manifestRelPath(module, version))

  /** True when a manifest exists for the module version. */
  def has(module: String, version: Version): Boolean =
    Files.isRegularFile(manifestPath(module, version))

  /** All versions of a module that have a manifest in the registry, unsorted. */
  def availableVersions(module: String): List[Version] =
    val prefix = module + "@"
    val dir = root.resolve(module).getParent
    val base = root
    val moduleDirName = module
    // Walk the registry for directories named `<module>@<version>`.
    if !Files.isDirectory(base) then return Nil
    val results = scala.collection.mutable.ListBuffer.empty[Version]
    val stream = Files.walk(base)
    try
      stream.iterator().asScala.foreach { p =>
        if Files.isDirectory(p) then
          val rel = base.relativize(p).toString
          if rel.startsWith(prefix) && !rel.substring(prefix.length).contains("/") then
            val vtext = rel.substring(prefix.length)
            if Files.isRegularFile(p.resolve("module.mod")) then
              results += Version.parse(vtext)
      }
    finally stream.close()
    results.toList

  /** Read and record a manifest by registry relative path. */
  def readManifestRel(relPath: String): Manifest =
    loadedPaths += relPath
    val text = new String(Files.readAllBytes(root.resolve(relPath)))
    ManifestParser.parse(text)

  /** Read and record a module version's manifest. */
  def readManifest(module: String, version: Version): Manifest =
    readManifestRel(manifestRelPath(module, version))

  /** Read a manifest from an arbitrary absolute path without recording it under
    * a registry relative name; used for the main module and local replace
    * targets. The recordedAs name, when given, is added to the loaded set.
    */
  def readManifestAt(path: Path, recordedAs: Option[String]): Manifest =
    recordedAs.foreach(loadedPaths += _)
    val text = new String(Files.readAllBytes(path))
    ManifestParser.parse(text)

  /** The registry relative paths of every manifest read so far, in read order. */
  def loaded: List[String] = loadedPaths.toList

object Registry:
  def open(rootDir: String): Registry = new Registry(Paths.get(rootDir).toAbsolutePath)
