Gate CLI
========

Rebuild::

    bash /app/environment/scripts/weld_bin.sh

Emit package::

    bash /app/environment/tools/mx_run.sh gate --out /app/output/mx_pack.json

``weld_bin.sh`` builds ``bin/mxbin`` then runs ``fold`` and ``bind``.
``mx_run.sh gate`` runs ``gauge`` then ``pack``.

Optional recover helper::

    bash /app/environment/scripts/recover.sh

That helper clears ``/app/output/stage`` contents and recreates the directory.
