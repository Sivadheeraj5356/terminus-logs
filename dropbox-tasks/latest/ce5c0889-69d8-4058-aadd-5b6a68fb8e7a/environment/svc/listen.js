'use strict';

const app = require('../svc/server');
const host = process.env.REF_HOST || '127.0.0.1';
const port = parseInt(process.env.REF_PORT || '7088', 10);

app.listen(port, host, () => {
  process.stdout.write(`ref-svc listening on ${host}:${port}\n`);
});
