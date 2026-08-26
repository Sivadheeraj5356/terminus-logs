package modverse

import java.nio.file.{Files, Paths, Path}

/** The modverse command line entry point. Subcommands and their JSON output are
  * documented in /app/app/docs/CLI.md. This dispatcher parses flags and prints
  * JSON; the domain logic it calls lives in the other source files.
  */
object Main:
  def main(args: Array[String]): Unit =
    if args.isEmpty then
      Console.err.println("usage: modverse <version|manifest|buildlist|graph> ...")
      sys.exit(2)
    val cmd = args.head
    val rest = args.tail
    try
      cmd match
        case "version"   => runVersion(rest)
        case "manifest"  => runManifest(rest)
        case "buildlist" => runBuildlist(rest)
        case "graph"     => runGraph(rest)
        case other =>
          Console.err.println(s"unknown subcommand: $other")
          sys.exit(2)
    catch
      case e: Throwable =>
        Console.err.println(s"error: ${e.getMessage}")
        sys.exit(1)

  private def flag(args: Array[String], name: String): Option[String] =
    val i = args.indexOf(name)
    if i >= 0 && i + 1 < args.length then Some(args(i + 1)) else None

  private def emit(out: Option[String], j: Json): Unit =
    val text = Json.render(j)
    out match
      case Some(p) => Files.write(Paths.get(p), text.getBytes)
      case None    => print(text)

  private def runVersion(args: Array[String]): Unit =
    flag(args, "--compare") match
      case Some(a) =>
        // --compare consumes two positional version strings after it.
        val i = args.indexOf("--compare")
        val b = args(i + 2)
        val c = VersionOrdering.compare(Version.parse(a), Version.parse(b))
        val norm = if c < 0 then -1L else if c > 0 then 1L else 0L
        emit(flag(args, "--out"), Json.obj("compare" -> Json.num(norm)))
      case None =>
        flag(args, "--sort") match
          case Some(list) =>
            val vs = list.split(",").toList.filter(_.nonEmpty).map(Version.parse)
            val sorted = vs.sorted(using VersionOrdering.asScalaOrdering)
            emit(
              flag(args, "--out"),
              Json.obj("sorted" -> Json.arr(sorted.map(v => Json.str(v.display))))
            )
          case None =>
            Console.err.println("version needs --compare A B or --sort list")
            sys.exit(2)

  private def runManifest(args: Array[String]): Unit =
    val file = flag(args, "--file").getOrElse {
      Console.err.println("manifest needs --file PATH"); sys.exit(2)
    }
    val text = new String(Files.readAllBytes(Paths.get(file)))
    val m = ManifestParser.parse(text)
    emit(flag(args, "--out"), manifestJson(m))

  private def manifestJson(m: Manifest): Json =
    Json.obj(
      "module" -> Json.str(m.module),
      "lang"   -> Json.str(m.lang.toString),
      "require" -> Json.arr(m.requires.map { r =>
        Json.obj(
          "path"     -> Json.str(r.path),
          "version"  -> Json.str(r.version.display),
          "indirect" -> Json.bool(r.indirect)
        )
      }),
      "replace" -> Json.arr(m.replaces.map { r =>
        Json.obj(
          "oldPath"    -> Json.str(r.oldPath),
          "oldVersion" -> Json.str(r.oldVersion.map(_.display).getOrElse("")),
          "newPath"    -> Json.str(r.newPath),
          "newVersion" -> Json.str(r.newVersion.map(_.display).getOrElse("")),
          "newIsLocal" -> Json.bool(r.newIsLocal)
        )
      }),
      "exclude" -> Json.arr(m.excludes.map { e =>
        Json.obj(
          "path"    -> Json.str(e.path),
          "version" -> Json.str(e.version.display)
        )
      })
    )

  private def runBuildlist(args: Array[String]): Unit =
    val (reg, main) = registryAndMain(args)
    val result = new Resolver(reg).resolve(main)
    emit(flag(args, "--out"), buildListJson(result))

  private def runGraph(args: Array[String]): Unit =
    val (reg, main) = registryAndMain(args)
    val result = new Resolver(reg).resolve(main)
    emit(
      flag(args, "--out"),
      Json.obj(
        "buildList" -> buildListObj(result),
        "loaded"    -> Json.arr(result.loaded.map(Json.str))
      )
    )

  private def registryAndMain(args: Array[String]): (Registry, Path) =
    val regDir = flag(args, "--registry").getOrElse {
      Console.err.println("needs --registry DIR"); sys.exit(2)
    }
    val mainPath = flag(args, "--main").getOrElse {
      Console.err.println("needs --main PATH"); sys.exit(2)
    }
    (Registry.open(regDir), Paths.get(mainPath).toAbsolutePath)

  private def buildListObj(result: ResolveResult): Json =
    val keys = result.buildList.keys.toList.sorted
    Json.objFrom(keys.map(k => k -> Json.str(result.buildList(k).display)))

  private def buildListJson(result: ResolveResult): Json =
    Json.obj("buildList" -> buildListObj(result))
