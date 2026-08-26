package modverse

/** A modverse version string. The raw form is kept exactly as written after a
  * leading `v` is stripped, so two versions are byte equal when their raw forms
  * match. The grammar and the total order are documented in
  * /app/app/docs/VERSIONS.md. Construction normalises the leading `v` only; it
  * does not validate or decompose the string, which is left to the ordering and
  * the comparison code that needs it.
  */
final case class Version(raw: String) extends Ordered[Version]:
  /** Spelling with the leading `v`, used everywhere versions are emitted. */
  def display: String = "v" + raw

  def compare(that: Version): Int = VersionOrdering.compare(this, that)

  override def toString: String = display

object Version:
  /** Build a Version from an on disk spelling, dropping a single leading `v`. */
  def parse(s: String): Version =
    val t = s.trim
    val body = if t.startsWith("v") then t.substring(1) else t
    Version(body)

/** The total order over version strings. The contract is in
  * /app/app/docs/VERSIONS.md: numeric core compared field by field, then within
  * an equal core a plain release in the middle, an incompatible release above
  * it, and prerelease and pseudo versions below it with pseudo versions at the
  * bottom.
  */
object VersionOrdering:
  def compare(a: Version, b: Version): Int =
    throw new NotImplementedError(
      "version ordering is not implemented yet"
    )

  /** A scala.math.Ordering view over compare, used by sorting in the CLI. */
  val asScalaOrdering: Ordering[Version] =
    (a: Version, b: Version) => compare(a, b)
