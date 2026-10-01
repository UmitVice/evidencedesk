import { test, expect } from "@playwright/test";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

// Tone is a microphone fixture. Transcription below is explicitly mocked;
// a separate hosted check supplies spoken audio to the real provider.
const path = join(
  mkdtempSync(join(tmpdir(), "evidencedesk-voice-")),
  "microphone.wav",
);
const wav = Buffer.alloc(44 + 96000);
wav.write("RIFF");
wav.writeUInt32LE(wav.length - 8, 4);
wav.write("WAVE", 8);
wav.write("fmt ", 12);
wav.writeUInt32LE(16, 16);
wav.writeUInt16LE(1, 20);
wav.writeUInt16LE(1, 22);
wav.writeUInt32LE(48000, 24);
wav.writeUInt32LE(96000, 28);
wav.writeUInt16LE(2, 32);
wav.writeUInt16LE(16, 34);
wav.write("data", 36);
wav.writeUInt32LE(96000, 40);
for (let i = 0; i < 48000; i++)
  wav.writeInt16LE(Math.floor(4000 * Math.sin(i / 12)), 44 + i * 2);
writeFileSync(path, wav);
test.use({
  permissions: ["microphone"],
  channel: "chromium",
  launchOptions: {
    args: [
      "--use-fake-device-for-media-stream",
      `--use-file-for-fake-audio-capture=${path}`,
    ],
  },
});

async function record(page: import("@playwright/test").Page) {
  await page
    .getByRole("button", { name: "Record Voice Note", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Stop & transcribe" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Analyze ticket", exact: true }),
  ).toBeDisabled();
  await expect(page.getByLabel("Sample ticket")).toBeDisabled();
  await expect(
    page.getByRole("status").filter({ hasText: "Recording…" }),
  ).toContainText("1 / 30", { timeout: 5000 });
  await page.getByRole("button", { name: "Stop & transcribe" }).click();
}

test("record, review transcript, bounded analysis, and standard approval persistence", async ({
  page,
}) => {
  await page.route("**/api/tickets/*/transcribe", async (route) => {
    expect(route.request().headers()["content-type"]).toBe("audio/wav");
    const body = route.request().postDataBuffer()!;
    expect(body.subarray(0, 4).toString()).toBe("RIFF");
    expect(body.length).toBeGreaterThan(8000);
    await route.fulfill({
      json: { text: "What should we do?", model: "fixture-transcription" },
    });
  });
  await page.goto("/workspace?sample=webhook");
  await record(page);
  await expect(
    page.getByLabel("Review your transcript before analysis"),
  ).toHaveValue("What should we do?");
  await expect(page.getByLabel("Your voice recording")).toBeVisible();
  await page.getByRole("button", { name: "Analyze voice question" }).click();
  // Generic fixture query has insufficient matching evidence. Keep that outcome honest.
  await expect(
    page.getByRole("heading", { name: "Not enough evidence" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Approve & save note" }),
  ).toHaveCount(0);
  await page.locator(".question-disclosure summary").click();
  await page.getByLabel("Optional question").selectOption("");
  await page
    .getByRole("button", { name: "Analyze ticket", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Approve & save note" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: /View source/ })
    .first()
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    "Webhook retry schedule",
  );
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Approve & save note" }).click();
  await expect(page.getByLabel("1 saved notes", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("1 saved notes", { exact: true })).toBeVisible();
});

test("transcription outage preserves recording and permits an explicit retry", async ({
  page,
}) => {
  let requests = 0;
  await page.route("**/api/tickets/*/transcribe", async (route) => {
    requests++;
    if (requests === 1)
      await route.fulfill({
        status: 503,
        json: {
          error: { message: "AI transcription is temporarily unavailable." },
        },
      });
    else
      await route.fulfill({
        json: { text: "What should we do?", model: "fixture-transcription" },
      });
  });
  await page.goto("/workspace?sample=export");
  await record(page);
  await expect(page.locator(".voice-error-banner")).toContainText(
    "AI transcription is temporarily unavailable.",
  );
  await expect(page.getByLabel("Your voice recording")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Analyze voice question" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Retry transcription" }).click();
  await expect(
    page.getByLabel("Review your transcript before analysis"),
  ).toHaveValue("What should we do?");
  expect(requests).toBe(2);
});

test("microphone denial recovers without a socket or upload", async ({
  page,
}) => {
  await page.addInitScript(() => {
    navigator.mediaDevices.getUserMedia = async () => {
      throw new DOMException("Denied", "NotAllowedError");
    };
  });
  let uploads = 0;
  page.on("request", (request) => {
    if (request.url().endsWith("/transcribe")) uploads++;
  });
  await page.goto("/workspace?sample=webhook");
  await page
    .getByRole("button", { name: "Record Voice Note", exact: true })
    .click();
  await expect(page.locator(".voice-error-banner")).toContainText(
    "Microphone access was denied",
  );
  await expect(
    page.getByRole("button", { name: "Record Voice Note", exact: true }),
  ).toBeEnabled();
  expect(uploads).toBe(0);
});
