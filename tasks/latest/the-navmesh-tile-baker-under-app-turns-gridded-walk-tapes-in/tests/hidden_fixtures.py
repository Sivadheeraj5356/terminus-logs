"""Hidden input fixtures only (tapes/manifest). No gold digests."""
from __future__ import annotations

import base64
import json
import zlib
from typing import Any

_BLOB = (
    "eNqlldtuozAURX/FYl5HFTZXV+JPkJAT3MYqMQyQDqHqv9fHXGwIzZTJC7J9tsPaxxvnwzmJPOcy"
    "OzMpXnjTOs/OL9QcuWS1KDORp23LKp41LT+n8pQ1vBasyCp2aXjaruaqXrE8a6oTr3XVmsHelh3f"
    "svzCCr3TzFStPQmZ1by5nPVGewrVWlQFN29dzFX9LPLhXSfx0oJguaAU5aEQfy6wJYe6PVXVvzx/"
    "5QMRVO2pquZVVmFYHwZqRTRlxvXSOJLO76mR0K7Gef5wRv0TLOiuvnLJa9byHA1S9F4WyiACQSqF"
    "FC2SXYJdJK/62ScUqd9XYxcp0ES9ZmgmOnZJgI5XePSJj+qEPAXonRUgVaKCHVCfkFSqXXqnHupe"
    "jbXQ1PC8SAcbo6fd3MRwxwtuhXQoO9S5CUZXePTw6DCIr1iJe5yEGp9o/NljuPR449Bb24pGB4vj"
    "f+QAbozsOQDvzgFMpFYQd3P6mpPYQYmnI/2m4QQarqypjkcjb2ybisBUeGsqnsH9tZMpNeZbf6Th"
    "4U8S722mYSvkmsy+o/ayUUCjQBZpMrqRBB/A/Blsalr0g6CaS3B307BuGrZTGqw+NwKnT+bTj+ev"
    "zdOEgVF6oPRAGYAyAmVkpYS63wcgHr1Yd/ZeM7FJ8hAAGmwF2VgJAZACoK8BafDvGNh/Gv8FGAOf"
    "iqkFuNVrAoABAAbmZsPkThrC9QJ2R2brn+iRgIzQ2CX3L2QK1D5QDxmmK2W4VFKjtBMSbNr5/PwC"
    "2czUhw=="
)

def load_hidden_fixtures() -> dict[str, Any]:
    raw = zlib.decompress(base64.b64decode(_BLOB.encode('ascii')))
    return json.loads(raw.decode('utf-8'))
