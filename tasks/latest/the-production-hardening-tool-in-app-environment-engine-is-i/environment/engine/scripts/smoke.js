'use strict';

const path = require('path');
const { hardenMediaInferenceDefaults } = require('../index');

const root = path.resolve(__dirname, '..');
hardenMediaInferenceDefaults(root, path.resolve(root, '..', 'dossier', 'incident-dossier.md'), path.resolve(root, '..', 'fixtures'), path.resolve(root, '..', '..', 'out'))
  .then(() => console.log('hardened defaults and generated audit artifacts'))
  .catch((error) => { console.error(error.stack || error.message); process.exitCode = 1; });
