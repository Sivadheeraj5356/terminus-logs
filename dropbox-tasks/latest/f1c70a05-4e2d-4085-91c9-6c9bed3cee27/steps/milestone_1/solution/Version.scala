package modverse

/** A modverse version string. The raw form is kept exactly as written after a
  * leading `v` is stripped, so two versions are byte equal when their raw forms
  * match. The grammar and the total order are documented in
  * /app/app/docs/VERSIONS.md.
  */
final case class Version(raw: String) extends Ordered[Version]:
  def display: String = "v" + raw

  def compare(that: Version): Int = VersionOrdering.compare(this, that)

  override def toString: String = display

object Version:
  def parse(s: String): Version =
    val t = s.trim
    val body = if t.startsWith("v") then t.substring(1) else t
    Version(body)

/** The total order over version strings, as specified in
  * /app/app/docs/VERSIONS.md.
  */
object VersionOrdering:
  private val pseudoRe = """\d{14}-[0-9a-f]{12}$""".r

  /** Decompose raw into (major, minor, patch, suffix, incompatible). suffix is
    * the prerelease text without the leading dash, or None.
    */
  private def split(raw: String): (Int, Int, Int, Option[String], Boolean) =
    var body = raw
    var incompat = false
    if body.endsWith("+incompatible") then
      incompat = true
      body = body.dropRight("+incompatible".length)
    if body.contains('+') then
      throw new IllegalArgumentException(s"bad build metadata: $raw")
    val (core, suffix) =
      val dash = body.indexOf('-')
      if dash < 0 then (body, None)
      else (body.substring(0, dash), Some(body.substring(dash + 1)))
    val parts = core.split('.')
    if parts.length != 3 then
      throw new IllegalArgumentException(s"bad numeric core: $raw")
    (parts(0).toInt, parts(1).toInt, parts(2).toInt, suffix, incompat)

  /** Rank within an equal core: 0 pseudo, 1 prerelease, 2 plain. Incompatible is
    * handled separately as the highest rank.
    */
  private def rank(suffix: Option[String]): Int = suffix match
    case None    => 2
    case Some(s) => if pseudoRe.findFirstIn(s).isDefined then 0 else 1

  private def isDigits(s: String): Boolean = s.nonEmpty && s.forall(_.isDigit)

  private def comparePrerelease(a: String, b: String): Int =
    val ai = a.split('.')
    val bi = b.split('.')
    val n = math.min(ai.length, bi.length)
    var i = 0
    while i < n do
      val x = ai(i); val y = bi(i)
      val xn = isDigits(x); val yn = isDigits(y)
      val c =
        if xn && yn then java.lang.Long.compare(x.toLong, y.toLong)
        else if xn && !yn then -1
        else if yn && !xn then 1
        else x.compareTo(y)
      if c != 0 then return c
      i += 1
    Integer.compare(ai.length, bi.length)

  private def pseudoKey(suffix: String): (Long, String) =
    val chunk = pseudoRe.findFirstIn(suffix).get
    val dash = chunk.indexOf('-')
    (chunk.substring(0, dash).toLong, chunk.substring(dash + 1))

  def compare(a: Version, b: Version): Int =
    if a.raw == b.raw then return 0
    val (amaj, amin, apat, asuf, ainc) = split(a.raw)
    val (bmaj, bmin, bpat, bsuf, binc) = split(b.raw)
    var c = Integer.compare(amaj, bmaj)
    if c != 0 then return c
    c = Integer.compare(amin, bmin)
    if c != 0 then return c
    c = Integer.compare(apat, bpat)
    if c != 0 then return c
    val arank = if ainc then 3 else rank(asuf)
    val brank = if binc then 3 else rank(bsuf)
    if arank != brank then return Integer.compare(arank, brank)
    arank match
      case 0 =>
        val (ats, ash) = pseudoKey(asuf.get)
        val (bts, bsh) = pseudoKey(bsuf.get)
        val tc = java.lang.Long.compare(ats, bts)
        if tc != 0 then tc else ash.compareTo(bsh)
      case 1 => comparePrerelease(asuf.get, bsuf.get)
      case _ => 0

  val asScalaOrdering: Ordering[Version] =
    (a: Version, b: Version) => compare(a, b)
