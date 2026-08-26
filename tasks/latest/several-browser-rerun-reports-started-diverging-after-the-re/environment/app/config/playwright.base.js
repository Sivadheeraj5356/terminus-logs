// config/playwright.base.js
// Base Playwright configuration reference used by plan generation.
// This file documents the expected structure of generated project configs.
// The actual config is generated dynamically by lib/planner.js.

/** @type {import('@playwright/test').PlaywrightTestConfig} */
const baseConfig = {
  // Timeout per test
  timeout: 30000,

  // Reporter configuration
  reporter: [
    ['json', { outputFile: 'logs/playwright-results.json' }],
    ['list'],
  ],

  // These are overridden per-project by the plan generator
  use: {
    headless: true,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },

  // Projects are injected by lib/planner.js at plan-generation time
  projects: [],
};

module.exports = baseConfig;
