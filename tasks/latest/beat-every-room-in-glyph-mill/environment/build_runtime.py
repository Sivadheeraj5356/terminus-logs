from pathlib import Path
import py_compile

src = Path('/app/glyph-mill/runtime_source.txt')
tmp = Path('/tmp/glyph_mill_runtime.py')
tmp.write_text(src.read_text())
py_compile.compile(str(tmp), cfile='/app/glyph-mill/glyph_mill_runtime.pyc', doraise=True)
src.unlink()
tmp.unlink()
