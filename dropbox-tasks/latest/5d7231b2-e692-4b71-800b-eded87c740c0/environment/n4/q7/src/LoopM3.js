'use strict';

const { vel_p3 } = require('./VelP3');
const { clk_h8 } = require('./ClkH8');
const { runTicks } = require('../../../r8/w1/src/EchoC');

function fnv1a32(buf) {
  let h = 0x811c9dc5 >>> 0;
  for (let i = 0; i < buf.length; i++) {
    h ^= buf[i];
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h.toString(16).padStart(8, '0');
}

function readFrame(raw) {
  if (raw.slice(0, 4).toString('ascii') !== 'K7FR') throw new Error('bad frame');
  const dim = raw.readUInt16LE(4);
  const seed = raw.readUInt32LE(6);
  let off = 10;
  const a0 = [];
  const b0 = [];
  for (let i = 0; i < dim; i++) { a0.push(raw.readFloatLE(off)); off += 4; }
  for (let i = 0; i < dim; i++) { b0.push(raw.readFloatLE(off)); off += 4; }
  const gs = raw.readFloatLE(off); off += 4;
  const ticks = raw.readUInt16LE(off); off += 2;
  const pause = raw.readUInt16LE(off);
  return { dim, seed, a0, b0, gs, ticks, pause, seedTag: fnv1a32(raw) };
}

function runSegment(frame, profile, ledger, viewA, viewB, from, to, wallBase, partsSeed) {
  return runTicks(frame, profile, (wall) => clk_h8(ledger, wall), wallBase, viewA, viewB, from, to, partsSeed);
}

function curveBytes(curve) {
  const buf = Buffer.alloc(curve.length * 8 + 4);
  buf.writeUInt32LE(curve.length, 0);
  for (let i = 0; i < curve.length; i++) buf.writeDoubleLE(curve[i], 4 + i * 8);
  return buf;
}

function unpackState(blob) {
  return vel_p3(blob, null, null);
}

function mkViews(frame) {
  return { viewA: Float64Array.from(frame.a0), viewB: Float64Array.from(frame.b0) };
}

function runUninterrupted(frame, profile) {
  const { viewA, viewB } = mkViews(frame);
  const ledger = { cont: 0 };
  const seg = runSegment(frame, profile, ledger, viewA, viewB, 1, frame.ticks, 1, []);
  return seg.curve;
}

function runResume(frame, profile) {
  const { viewA, viewB } = mkViews(frame);
  const ledger = { cont: 0 };
  const first = runSegment(frame, profile, ledger, viewA, viewB, 1, frame.pause, 1, []);
  const packed = vel_p3(null, first.viewA, first.viewB);
  ledger.cont = frame.pause;
  const restored = unpackState(packed);
  const second = runSegment(
    frame,
    profile,
    ledger,
    restored.viewA,
    restored.viewB,
    frame.pause + 1,
    frame.ticks,
    1,
    first.parts,
  );
  return first.curve.concat(second.curve);
}

module.exports = {
  readFrame,
  runSegment,
  runUninterrupted,
  runResume,
  curveBytes,
  fnv1a32,
};
