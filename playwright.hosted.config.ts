import { defineConfig } from "@playwright/test";

const origin = process.env.HOSTED_URL;
if (
  ![
    "https://evidencedesk-web.vercel.app",
    "https://evidencedesk-web-git-dev-umitvices-projects.vercel.app",
  ].includes(origin || "")
)
  throw new Error(
    "Set HOSTED_URL to the existing dev or production web origin.",
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
