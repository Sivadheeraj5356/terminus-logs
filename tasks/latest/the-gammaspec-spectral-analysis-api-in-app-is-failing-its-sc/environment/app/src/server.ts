import express from "express";
import fs from "fs";
import path from "path";
import { batchFit } from "./batch";
import { bootstrapSpectrum } from "./bootstrap";
import { fitSpectrum } from "./fit";
import { diagnostics } from "./diagnostics";
import { isotopeScreen } from "./screening";

const app = express();
app.use(express.json({ limit: "3mb" }));

app.get("/health", (_req, res) => {
  res.json({ ok: true, service: "gammaspec-api" });
});

app.post("/fit", (req, res) => {
  try {
    res.json(fitSpectrum(req.body));
  } catch (error) {
    res.status(400).json({ error: error instanceof Error ? error.message : String(error) });
  }
});

app.post("/bootstrap", (req, res) => {
  try {
    res.json(bootstrapSpectrum(req.body));
  } catch (error) {
    res.status(400).json({ error: error instanceof Error ? error.message : String(error) });
  }
});

app.post("/batch-fit", (req, res) => {
  try {
    res.json(batchFit(req.body));
  } catch (error) {
    res.status(400).json({ error: error instanceof Error ? error.message : String(error) });
  }
});


app.post("/diagnostics", (req, res) => {
  try {
    res.json(diagnostics(req.body));
  } catch (error) {
    res.status(400).json({ error: error instanceof Error ? error.message : String(error) });
  }
});

app.post("/isotope-screen", (req, res) => {
  try {
    res.json(isotopeScreen(req.body));
  } catch (error) {
    res.status(400).json({ error: error instanceof Error ? error.message : String(error) });
  }
});

app.get("/compliance", (_req, res) => {
  const matrixPath = path.join(process.cwd(), "output", "compliance_matrix.json");
  if (!fs.existsSync(matrixPath)) {
    res.status(404).json({ error: "compliance matrix not written" });
    return;
  }
  res.type("application/json").send(fs.readFileSync(matrixPath, "utf8"));
});

const port = Number(process.env.PORT ?? "3000");
app.listen(port, () => {
  console.log(`GammaSpec API listening on ${port}`);
});
