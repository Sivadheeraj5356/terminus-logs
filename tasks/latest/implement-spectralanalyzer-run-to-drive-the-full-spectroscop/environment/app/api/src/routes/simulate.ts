import { Router, Request, Response } from 'express';
import { simulateOscillator, SimulateParams } from '../oscillator';

const router: Router = Router();

router.post('/', (req: Request, res: Response) => {
  const { sampleRateHz, durationSec, damping, naturalFreqHz } = req.body;

  if (!sampleRateHz || !durationSec || damping === undefined || !naturalFreqHz) {
    res.status(400).json({ error: 'Missing required parameters' });
    return;
  }

  const params: SimulateParams = {
    sampleRateHz: Number(sampleRateHz),
    durationSec: Number(durationSec),
    damping: Number(damping),
    naturalFreqHz: Number(naturalFreqHz)
  };

  const result = simulateOscillator(params);
  res.json(result);
});

export default router;
