import { defineConfig } from "@playwright/test";

const origin = process.env.HOSTED_URL;
if (
  ![
    "https://evidencedesk.umitvice.com",
  ].includes(origin || "")
)
  throw new Error(
    "Set HOSTED_URL to the production web origin.",
  );

export default defineConfig({
  testDir: "./tests/hosted",
  workers: 1,
  retries: 0,
  timeout: 120_000,
  reporter: "list",
  outputDir: "test-results/hosted",
  use: { baseURL: origin, trace: "off", screenshot: "off", video: "off" },
});
