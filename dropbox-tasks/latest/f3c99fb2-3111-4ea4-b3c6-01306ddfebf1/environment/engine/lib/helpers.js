'use strict';

const fs = require('fs');
const path = require('path');
const tf = require('@tensorflow/tfjs');
const config = require('../config/inference');

const LABELS = config.service.labels;
const FEATURE_SIZE = 8;
let cachedModel = null;

async function loadModel(repoRoot) {
  if (cachedModel) return cachedModel;
  const root = repoRoot || path.resolve(__dirname, '..');
  const modelPath = path.resolve(root, config.service.modelPath);
  const modelJson = JSON.parse(fs.readFileSync(modelPath, 'utf8'));
  const weightPath = path.resolve(path.dirname(modelPath), modelJson.weightsManifest[0].paths[0]);
  const bytes = fs.readFileSync(weightPath);
  const weightData = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
  cachedModel = await tf.loadLayersModel(tf.io.fromMemory({
    modelTopology: modelJson.modelTopology,
    weightSpecs: modelJson.weightsManifest[0].weights,
    weightData,
  }));
  return cachedModel;
}

function imageToFeatureVector(imagePath) {
  const bytes = fs.readFileSync(imagePath);
  const features = new Array(FEATURE_SIZE).fill(0);
  if (!bytes.length) return features;
  const bucketSize = bytes.length / FEATURE_SIZE;
  const counts = new Array(FEATURE_SIZE).fill(0);
  for (let index = 0; index < bytes.length; index += 1) {
    const bucket = Math.min(FEATURE_SIZE - 1, Math.floor(index / bucketSize));
    features[bucket] += bytes[index];
    counts[bucket] += 1;
  }
  return features.map((total, index) => counts[index] ? total / counts[index] / 255 : 0);
}

async function evaluateFixture(imagePath, repoRoot) {
  const model = await loadModel(repoRoot);
  const input = tf.tensor2d([imageToFeatureVector(imagePath)], [1, FEATURE_SIZE]);
  const output = model.predict(input);
  const probabilities = Array.from(await output.data());
  input.dispose();
  output.dispose();
  let bestIndex = 0;
  for (let index = 1; index < probabilities.length; index += 1) if (probabilities[index] > probabilities[bestIndex]) bestIndex = index;
  return { label: LABELS[bestIndex], confidence: Math.round(probabilities[bestIndex] * 1e6) / 1e6 };
}

module.exports = { loadModel, imageToFeatureVector, evaluateFixture, LABELS, FEATURE_SIZE };
