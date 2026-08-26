import express, { Application } from 'express';
import healthRouter from './routes/health';
import metadataRouter from './routes/metadata';
import simulateRouter from './routes/simulate';

const app: Application = express();
app.use(express.json());

app.use('/health', healthRouter);
app.use('/metadata', metadataRouter);
app.use('/simulate', simulateRouter);

const PORT = 3000;
app.listen(PORT, () => {
  console.log(`Sensor simulation API listening on port ${PORT}`);
});

export default app;
