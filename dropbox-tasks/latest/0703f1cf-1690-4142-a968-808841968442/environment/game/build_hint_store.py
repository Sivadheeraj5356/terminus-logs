import json
from pathlib import Path
import lmdb

root = Path('/app/glyph-mill')
rooms = json.loads((root / 'seed_rooms.json').read_text())
env = lmdb.open(str(root / 'hints.lmdb'), map_size=10_485_760, max_dbs=1)
with env.begin(write=True) as txn:
    txn.put(b'rooms', json.dumps(sorted(rooms)).encode())
    for room_id, payload in rooms.items():
        payload = dict(payload)
        payload['id'] = room_id
        txn.put(f'room:{room_id}'.encode(), json.dumps(payload, sort_keys=True).encode())
env.sync()
env.close()
