import { fileURLToPath, URL } from "node:url";

import { defineConfig, devices } from "@playwright/test";

const repositoryRoot = fileURLToPath(new URL("../..", import.meta.url));

export default defineConfig({
  testDir: fileURLToPath(new URL("./tests/browser", import.meta.url)),
  timeout: 60_000,
  workers: 1,
  webServer: {
    command: ".venv/bin/python -m uvicorn src.mes.api:app --host 127.0.0.1 --port 8010 --no-access-log",
    cwd: repositoryRoot,
    env: {
      ...process.env,
      MES_DB_PATH: "data/mes_factory_twin_browser.sqlite3",
    },
    url: "http://127.0.0.1:8010/api/v2/factory-twin/layout",
    reuseExistingServer: true,
    timeout: 120_000,
  },
  use: {
    baseURL: "http://127.0.0.1:8010",
    headless: true,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
