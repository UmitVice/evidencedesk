import { readFileSync } from "node:fs";
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// Explicit release smoke only: two live analyses, no retries or quota changes.
test("hosted sources, approval persistence, rejection, and responsive accessibility", async ({
  page,
  context,
  baseURL,
}) => {
  if (process.env.HOSTED_AUTH_FILE) {
    const auth = JSON.parse(readFileSync(process.env.HOSTED_AUTH_FILE, "utf8"));
    expect(auth.origin).toBe(baseURL);
    // Existing automation access stays in the test process, scoped to this origin.
    // Never put it in a URL, page script, screenshot, trace, or logged output.
    await page.route(`${baseURL}/**`, (route) =>
      route.continue({
        headers: { ...route.request().headers(), ...auth.headers },
      }),
    );
  }
  const errors: string[] = [];
  const analyses: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => {
    if (request.url().endsWith("/analyze")) analyses.push(request.url());
  });
  const screenshots =
    process.env.HOSTED_SCREENSHOTS || "test-results/hosted/screenshots";
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Turn a support ticket into a reviewed note.",
  );
  await page.screenshot({
    path: `${screenshots}/landing-desktop.png`,
    fullPage: true,
  });
  await page.getByRole("link", { name: /Webhook retry failure/ }).click();
  await expect(
    page.getByRole("button", { name: "Analyze ticket", exact: true }),
  ).toBeVisible();
  expect(analyses).toHaveLength(0);
  await page
    .getByRole("button", { name: "Analyze ticket", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Approve & save note" }),
  ).toBeEnabled({ timeout: 55_000 });
  await expect(page.getByTestId("analysis-mode")).toHaveText("Live AI");
  const draft = await page.locator(".proposed-note").innerText();
  await expect(page.locator(".saved-note")).toHaveCount(0);
  // A draft can arrive before the final ticket refresh finishes.
  // Wait for the rendered source controls before enumerating the live result.
  await expect(
    page.getByRole("button", { name: /View source/ }).first(),
  ).toBeVisible();
  const sources = await page.getByRole("button", { name: /View source/ }).all();
  expect(sources.length).toBeGreaterThan(0);
  for (const source of sources) {
    await source.click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.locator(".exact-quote")).toBeVisible();
    const quote = await dialog.locator(".exact-quote").innerText();
    await expect(dialog.locator(".source-passage")).toContainText(quote);
    await page.keyboard.press("Escape");
    await expect(source).toBeFocused();
  }
  await page.screenshot({
    path: `${screenshots}/review-desktop.png`,
    fullPage: true,
  });
  await page.reload();
  await expect(page.locator(".proposed-note")).toHaveText(draft);
  await page.getByRole("button", { name: "Approve & save note" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Note approved and saved",
  );
  await page.reload();
  await expect(page.locator(".saved-note blockquote")).toHaveText(draft);
  await expect(page.locator(".saved-note")).toHaveCount(1);
  const cookie = (await context.cookies()).find(
    (cookie) => cookie.name === "evidencedesk_session",
  );
  expect(cookie?.httpOnly).toBe(true);
  expect(cookie?.secure).toBe(true);
  expect(cookie?.sameSite).toBe("Lax");
  await page.setViewportSize({ width: 375, height: 812 });
  await page
    .getByLabel("Sample ticket")
    .selectOption({ label: "Expired API credential" });
  await expect(
    page.getByRole("heading", {
      name: "API requests fail with an expired credential",
    }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Analyze ticket", exact: true })
    .click();
  await expect(page.getByRole("button", { name: "Reject draft" })).toBeVisible({
    timeout: 55_000,
  });
  await expect(
    page.getByRole("button", { name: "Reject draft" }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: /View source/ })
    .first()
    .click();
  await expect(page.getByRole("dialog").locator(".exact-quote")).toBeVisible();
  await page.screenshot({
    path: `${screenshots}/source-mobile.png`,
    fullPage: false,
  });
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Reject draft" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Draft rejected. No note saved.",
  );
  await page.reload();
  await expect(page.getByRole("status")).toContainText(
    "Draft rejected. No note saved.",
  );
  await expect(page.locator(".saved-note")).toHaveCount(0);
  await page.screenshot({
    path: `${screenshots}/rejected-mobile.png`,
    fullPage: true,
  });
  const scan = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(scan.violations).toEqual([]);
  for (const width of [320, 375, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }
  await page.getByRole("link", { name: "Evaluations", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "How reliable are the suggestions?" }),
  ).toBeVisible();
  expect(analyses).toHaveLength(2);
  expect(errors).toEqual([]);
});
