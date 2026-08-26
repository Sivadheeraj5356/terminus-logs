'use strict';

const os = require('os');
const path = require('path');
const express = require('express');
const cors = require('cors');
const multer = require('multer');
const config = require('./config/inference');
const { evaluateFixture } = require('./lib/helpers');
const { applyThresholds } = require('./lib/runtime/policy');
const { redactTelemetry } = require('./lib/telemetry/redact');

function createApp(runtimeConfig = config, telemetrySink = () => {}) {
  const app = express();
  app.use(express.json());
  app.use(cors({ origin: runtimeConfig.cors.origin, methods: runtimeConfig.cors.methods, credentials: runtimeConfig.cors.credentials }));
  const upload = multer({ dest: path.join(os.tmpdir(), 'media-moderation-uploads'), limits: { fileSize: runtimeConfig.maxUploadBytes } });
  app.get('/health', (req, res) => res.status(200).json({ status: 'ok', service: runtimeConfig.service.name }));
  app.post('/moderate', upload.single('image'), async (req, res) => {
    if (!req.file) return res.status(400).json({ error: 'missing image upload (field "image")' });
    try {
      const decision = await evaluateFixture(req.file.path);
      telemetrySink(runtimeConfig.telemetryRedactionEnabled ? redactTelemetry({ request: req }, runtimeConfig.telemetryRedactedFields) : { request: req });
      return res.status(200).json(applyThresholds(decision, runtimeConfig));
    } catch (error) { return res.status(500).json({ error: 'inference failed', detail: String(error.message || error) }); }
  });
  if (runtimeConfig.debugInferenceEnabled) app.post('/debug/infer', async (req, res) => {
    try { return res.status(200).json({ decision: await evaluateFixture(req.body.imagePath), debug: true }); }
    catch (error) { return res.status(500).json({ error: 'inference failed', detail: String(error.message || error) }); }
  });
  return app;
}

function start() { return createApp().listen(config.service.port, '0.0.0.0'); }
if (require.main === module) start();
module.exports = { createApp, start };
