package modverse

/** Minimal JSON value model and serialiser. Stdlib only. Objects preserve key
  * insertion order so output is stable. This is plumbing for the CLI and not the
  * work of the task.
  */
enum Json:
  case JStr(s: String)
  case JNum(n: Long)
  case JBool(b: Boolean)
  case JArr(items: List[Json])
  case JObj(fields: List[(String, Json)])

object Json:
  def str(s: String): Json = JStr(s)
  def num(n: Long): Json = JNum(n)
  def bool(b: Boolean): Json = JBool(b)
  def arr(items: List[Json]): Json = JArr(items)
  def obj(fields: (String, Json)*): Json = JObj(fields.toList)
  def objFrom(fields: List[(String, Json)]): Json = JObj(fields)

  private def escape(s: String): String =
    val sb = new StringBuilder
    s.foreach {
      case '"'  => sb.append("\\\"")
      case '\\' => sb.append("\\\\")
      case '\n' => sb.append("\\n")
      case '\r' => sb.append("\\r")
      case '\t' => sb.append("\\t")
      case c    => sb.append(c)
    }
    sb.toString

  /** Pretty print with two space indentation. */
  def render(j: Json): String =
    val sb = new StringBuilder
    go(j, 0, sb)
    sb.append('\n')
    sb.toString

  private def pad(n: Int, sb: StringBuilder): Unit =
    var i = 0
    while i < n do { sb.append("  "); i += 1 }

  private def go(j: Json, indent: Int, sb: StringBuilder): Unit = j match
    case JStr(s)  => sb.append('"').append(escape(s)).append('"')
    case JNum(n)  => sb.append(n.toString)
    case JBool(b) => sb.append(if b then "true" else "false")
    case JArr(items) =>
      if items.isEmpty then sb.append("[]")
      else
        sb.append("[\n")
        items.zipWithIndex.foreach { case (it, i) =>
          pad(indent + 1, sb)
          go(it, indent + 1, sb)
          if i < items.length - 1 then sb.append(',')
          sb.append('\n')
        }
        pad(indent, sb); sb.append(']')
    case JObj(fields) =>
      if fields.isEmpty then sb.append("{}")
      else
        sb.append("{\n")
        fields.zipWithIndex.foreach { case ((k, v), i) =>
          pad(indent + 1, sb)
          sb.append('"').append(escape(k)).append("\": ")
          go(v, indent + 1, sb)
          if i < fields.length - 1 then sb.append(',')
          sb.append('\n')
        }
        pad(indent, sb); sb.append('}')
