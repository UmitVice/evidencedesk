import { readFileSync } from "node:fs";
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// Explicit opt-in: actual spoken audio, real hosted transcription and RAG.
// One transcription + one analysis; never retry automatically or reset quotas.
test.use({
  channel: "chromium",
  permissions: ["microphone"],
  launchOptions: {
    args: [
      "--use-fake-device-for-media-stream",
      ...(process.env.HOSTED_VOICE_AUDIO
        ? [
            `--use-file-for-fake-audio-capture=${process.env.HOSTED_VOICE_AUDIO}`,
          ]
        : []),
    ],
  },
});
test("hosted spoken recording, transcript, sources, approval and persisted note", async ({
  page,
  baseURL,
}) => {
  test.skip(
    !process.env.HOSTED_VOICE_AUDIO,
    "Provide a spoken WAV microphone fixture explicitly.",
  );
  if (process.env.HOSTED_AUTH_FILE) {
    const auth = JSON.parse(readFileSync(process.env.HOSTED_AUTH_FILE, "utf8"));
    expect(auth.origin).toBe(baseURL);
    await page.route(`${baseURL}/**`, (route) =>
      route.continue({
        headers: { ...route.request().headers(), ...auth.headers },
      }),
    );
  }
  const errors: string[] = [];
  let sockets = 0;
  let transcriptions = 0;
  let analyses = 0;
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("websocket", () => sockets++);
  page.on("request", (r) => {
    if (r.url().endsWith("/transcribe")) transcriptions++;
    if (r.url().endsWith("/analyze")) analyses++;
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/workspace?sample=webhook");
  await expect(page.getByTestId("analysis-mode")).toHaveText("Live AI");
  await page
    .getByRole("button", { name: "Record Voice Note", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Stop & transcribe" }),
  ).toBeVisible();
  await expect(
    page.getByRole("status").filter({ hasText: "Recording…" }),
  ).toContainText("8 / 30", { timeout: 12000 });
  await page.getByRole("button", { name: "Stop & transcribe" }).click();
  const transcript = page.getByLabel("Review your transcript before analysis");
  await expect(transcript).toBeVisible({ timeout: 50000 });
  expect((await transcript.inputValue()).toLowerCase()).toContain("webhook");
  expect((await transcript.inputValue()).toLowerCase()).toContain("recover");
  const audio = page.getByLabel("Your voice recording");
  await expect(audio).toBeVisible();
  await expect
    .poll(() => audio.evaluate((a: HTMLAudioElement) => a.duration))
    .toBeGreaterThan(6);
  expect(analyses).toBe(0);
  const directory =
    process.env.HOSTED_SCREENSHOTS || "test-results/hosted/voice";
  await page.screenshot({
    path: `${directory}/voice-transcript-desktop.png`,
    fullPage: true,
  });
  for (const width of [320, 375, 768]) {
    await page.setViewportSize({ width, height: 900 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    await expect(transcript).toBeVisible();
  }
  await page.screenshot({
    path: `${directory}/voice-transcript-mobile.png`,
    fullPage: true,
  });
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole("button", { name: "Analyze voice question" }).click();
  await expect(
    page.getByRole("button", { name: "Approve & save note" }),
  ).toBeEnabled({ timeout: 55000 });
  const draft = await page.locator(".proposed-note").innerText();
  await expect(page.locator(".saved-note")).toHaveCount(0);
  const sources = page.getByRole("button", { name: /View source/ });
  await expect(sources.first()).toBeVisible();
  for (const button of await sources.all()) {
    await button.click();
    await expect(page.getByRole("dialog")).toContainText("Original source");
    await page.keyboard.press("Escape");
  }
  await page.getByRole("button", { name: "Approve & save note" }).click();
  await expect(page.locator(".saved-note blockquote")).toHaveText(draft);
  await page.reload();
  await expect(page.locator(".saved-note blockquote")).toHaveText(draft);
  await expect(page.getByRole("status")).toContainText(
    "Note approved and saved",
  );
  await page.screenshot({
    path: `${directory}/voice-approved-persisted.png`,
    fullPage: true,
  });
  expect(transcriptions).toBe(1);
  expect(analyses).toBe(1);
  expect(sockets).toBe(0);
  expect(errors).toEqual([]);
});
