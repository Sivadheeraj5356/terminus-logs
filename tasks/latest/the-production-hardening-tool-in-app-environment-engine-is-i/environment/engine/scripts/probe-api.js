'use strict';

const { createApp } = require('../server');

const server = createApp().listen(0, () => {
  console.log(`probe server listening on ${server.address().port}`);
  server.close();
});
