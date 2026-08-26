import { Router, Request, Response } from 'express';

const router: Router = Router();

router.get('/', (_req: Request, res: Response) => {
  res.json({
    apiVersion: '1.0.0',
    simulator: 'damped-oscillator',
    supportedUnits: ['m/s^2'],
    fftMethod: 'direct',
    maxSamples: 65536
  });
});

export default router;
