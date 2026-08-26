'use strict';

const express = require('express');
const router = express.Router();

const DISPUTES = {
  102: { round_id: 102, ruling_side: 'side_b', cabinet_hint: 'blue-cab', note: 'timing' },
  103: { round_id: 103, ruling_side: 'side_a', cabinet_hint: 'red-cab', note: 'frame_lock' },
};

const CABINET_META = {
  'red-cab': { firmware: '1.4.2' },
  'blue-cab': { firmware: '1.4.1' },
};

router.get('/disputes', (req, res) => {
  const raw = req.query.round_ids || '';
  const ids = raw.split(',').map((s) => parseInt(s.trim(), 10)).filter((n) => !Number.isNaN(n));
  const disputes = ids
    .filter((id) => DISPUTES[id])
    .map((id) => DISPUTES[id])
    .sort((a, b) => a.round_id - b.round_id);
  res.json({
    disputes,
    cabinet_meta: CABINET_META,
  });
});

module.exports = router;
