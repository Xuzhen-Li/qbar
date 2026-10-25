import { defineConfig } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(here, "..");
const port = 4173;

export default defineConfig({
  testDir: here,
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0,
  timeout: 180000,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:" + port,
    headless: true,
  },
  webServer: {
    command:
      "python3 -m http.server " +
      port +
      " --bind 127.0.0.1 --directory " +
      JSON.stringify(webRoot),
    url: "http://127.0.0.1:" + port + "/",
    reuseExistingServer: false,
    timeout: 30000,
  },
});
