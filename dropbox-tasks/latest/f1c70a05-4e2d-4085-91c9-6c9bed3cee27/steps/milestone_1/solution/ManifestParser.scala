package modverse

/** Parses a manifest file into the typed Manifest model. The grammar is in
  * /app/app/docs/MANIFEST.md.
  */
object ManifestParser:
  def parse(text: String): Manifest =
    var module = ""
    var lang = LangVersion(0, 0)
    val requires = scala.collection.mutable.ListBuffer.empty[Require]
    val replaces = scala.collection.mutable.ListBuffer.empty[Replace]
    val excludes = scala.collection.mutable.ListBuffer.empty[Exclude]

    val lines = text.split("\n", -1)
    var i = 0

    def isComment(s: String): Boolean = s.startsWith("//")

    def readBlock(parseEntry: String => Unit): Unit =
      var done = false
      while i < lines.length && !done do
        val bs = lines(i).trim
        i += 1
        if bs == ")" then done = true
        else if bs.isEmpty || isComment(bs) then ()
        else parseEntry(bs)

    while i < lines.length do
      val raw = lines(i)
      i += 1
      val s = raw.trim
      if s.isEmpty || isComment(s) then ()
      else if s.startsWith("module ") then module = s.substring("module ".length).trim
      else if s.startsWith("lang ") then
        lang = LangVersion.parse(s.substring("lang ".length).trim)
      else if s.startsWith("require") then
        val rest = s.substring("require".length).trim
        if rest == "(" then readBlock(e => requires += parseRequire(e))
        else requires += parseRequire(rest)
      else if s.startsWith("replace") then
        val rest = s.substring("replace".length).trim
        if rest == "(" then readBlock(e => replaces += parseReplace(e))
        else replaces += parseReplace(rest)
      else if s.startsWith("exclude") then
        val rest = s.substring("exclude".length).trim
        if rest == "(" then readBlock(e => excludes += parseExclude(e))
        else excludes += parseExclude(rest)
      else throw new IllegalArgumentException(s"unrecognised manifest line: $s")

    Manifest(module, lang, requires.toList, replaces.toList, excludes.toList)

  /** Strip a trailing comment, returning the content and whether the comment was
    * the literal `indirect` marker.
    */
  private def stripComment(line: String): (String, Boolean) =
    val idx = line.indexOf("//")
    if idx < 0 then (line, false)
    else (line.substring(0, idx), line.substring(idx + 2).trim == "indirect")

  private def parseRequire(s: String): Require =
    val (content, indirect) = stripComment(s)
    val toks = content.trim.split("\\s+").filter(_.nonEmpty)
    if toks.length != 2 then
      throw new IllegalArgumentException(s"bad require entry: $s")
    Require(toks(0), Version.parse(toks(1)), indirect)

  private def parseReplace(s: String): Replace =
    val (content, _) = stripComment(s)
    val arrow = content.indexOf("=>")
    if arrow < 0 then throw new IllegalArgumentException(s"bad replace entry: $s")
    val left = content.substring(0, arrow).trim.split("\\s+").filter(_.nonEmpty)
    val right = content.substring(arrow + 2).trim.split("\\s+").filter(_.nonEmpty)
    val oldPath = left(0)
    val oldVersion = if left.length >= 2 then Some(Version.parse(left(1))) else None
    val newPath = right(0)
    val isLocal = newPath.startsWith("./") || newPath.startsWith("../")
    val newVersion =
      if !isLocal && right.length >= 2 then Some(Version.parse(right(1))) else None
    Replace(oldPath, oldVersion, newPath, newVersion, isLocal)

  private def parseExclude(s: String): Exclude =
    val (content, _) = stripComment(s)
    val toks = content.trim.split("\\s+").filter(_.nonEmpty)
    if toks.length != 2 then
      throw new IllegalArgumentException(s"bad exclude entry: $s")
    Exclude(toks(0), Version.parse(toks(1)))
