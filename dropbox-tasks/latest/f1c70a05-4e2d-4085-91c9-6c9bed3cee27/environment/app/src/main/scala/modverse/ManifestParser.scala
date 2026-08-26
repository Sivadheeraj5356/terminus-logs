package modverse

/** Parses a manifest file into the typed Manifest model. The grammar, including
  * the single line and block forms of require, replace, and exclude, the lang
  * line, the `// indirect` marker, and the local path target rule, is documented
  * in /app/app/docs/MANIFEST.md.
  */
object ManifestParser:
  /** Parse the manifest text into a Manifest. */
  def parse(text: String): Manifest =
    throw new NotImplementedError(
      "manifest parsing is not implemented yet"
    )
