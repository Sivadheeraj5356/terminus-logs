package modverse

// Typed model for the modverse manifest and version domain. These value types
// are the shared vocabulary every layer of the resolver speaks. The fields are
// fixed by the JSON contract in /app/app/docs/CLI.md and the grammar in
// /app/app/docs/MANIFEST.md, so the shapes here are stable and not the work of
// this task.

/** A required dependency edge. The version is the minimum the requiring module
  * asks for. The indirect flag records the trailing marker from the manifest.
  */
final case class Require(path: String, version: Version, indirect: Boolean)

/** A replace directive. An empty oldVersion means every version of oldPath. A
  * local target sets newIsLocal and carries the filesystem path in newPath with
  * an empty newVersion.
  */
final case class Replace(
    oldPath: String,
    oldVersion: Option[Version],
    newPath: String,
    newVersion: Option[Version],
    newIsLocal: Boolean
)

/** An exclude directive naming one exact module version to drop. */
final case class Exclude(path: String, version: Version)

/** A parsed manifest. lang defaults to LangVersion(0, 0) when no lang line is
  * present. The directive lists preserve file order.
  */
final case class Manifest(
    module: String,
    lang: LangVersion,
    requires: List[Require],
    replaces: List[Replace],
    excludes: List[Exclude]
)

/** The two field lang generation a manifest declares, compared field by field as
  * integers.
  */
final case class LangVersion(major: Int, minor: Int) extends Ordered[LangVersion]:
  def compare(that: LangVersion): Int =
    val c = Integer.compare(major, that.major)
    if c != 0 then c else Integer.compare(minor, that.minor)
  override def toString: String = s"$major.$minor"

object LangVersion:
  /** Parse a two field dotted lang value such as "1.21". */
  def parse(s: String): LangVersion =
    val parts = s.trim.split('.')
    if parts.length != 2 then
      throw new IllegalArgumentException(s"bad lang value: $s")
    LangVersion(parts(0).toInt, parts(1).toInt)
