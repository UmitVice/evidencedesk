import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const screenshotDir = process.env.SCREENSHOT_DIR || "test-results/screenshots";

const browserErrors = new WeakMap<Page, string[]>();
test.beforeEach(async ({ page }) => {
  const errors: string[] = [];
  browserErrors.set(page, errors);
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (
      /hydration|hydrated/i.test(message.text()) &&
      ["error", "warning"].includes(message.type())
    )
      errors.push(message.text());
  });
});
test.afterEach(async ({ page }) => {
  expect(browserErrors.get(page) ?? []).toEqual([]);
});

test("source inspection, pending reload, approval and persisted note", async ({
  page,
  context,
}) => {
  await page.goto("/");
  await page.getByRole("link", { name: /Webhook retry failure/ }).click();
  await expect(
    page.getByRole("heading", {
      name: "Webhook delivery stopped after retries",
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Analyze ticket" }).click();
  await expect(
    page.getByRole("button", { name: "Approve & save note" }),
  ).toBeVisible();
  await page.getByRole("button", { name: /View source/ }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("dialog")).toContainText(
    "Webhook retry schedule",
  );
  await expect(page.getByRole("dialog")).toContainText(
    "AI suggestion under review",
  );
  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(
      page.getByRole("dialog").getByRole("button", { name: "Close source" }),
    ).toBeInViewport();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: `${screenshotDir}/evidence-${width}.png`,
      fullPage: false,
    });
  }
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: /View source/ })).toBeFocused();
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Approve & save note" }),
  ).toBeVisible();
  for (const width of [375, 768]) {
    await page.setViewportSize({ width, height: 900 });
    const approve = page.getByRole("button", { name: "Approve & save note" });
    await approve.scrollIntoViewIfNeeded();
    await expect(approve).toBeInViewport();
    await page.screenshot({
      path: `${screenshotDir}/workspace-${width}.png`,
      fullPage: true,
    });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole("button", { name: "Approve & save note" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Note approved and saved",
  );
  await page.reload();
  await expect(page.getByRole("status")).toContainText(
    "Note approved and saved",
  );
  const cookie = (await context.cookies()).find(
    (c) => c.name === "evidencedesk_session",
  );
  expect(cookie?.httpOnly).toBe(true);
  expect(cookie?.sameSite).toBe("Lax");
  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
  }
  await page.screenshot({
    path: `${screenshotDir}/workspace.png`,
    fullPage: true,
  });
});

test("rejection and insufficient evidence do not create notes", async ({
  page,
}) => {
  await page.goto("/workspace");
  await page.getByRole("button", { name: "Open demo workspace" }).click();
  await page.getByRole("button", { name: "Analyze ticket" }).click();
  await page.getByRole("button", { name: "Reject draft", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Draft rejected");
  await expect(
    page.getByText("No saved notes yet.", { exact: false }),
  ).toBeVisible();
  await page.getByText("Ask a different question", { exact: false }).click();
  await page
    .getByLabel("Optional question")
    .selectOption("Can RelayNest configure SSO?");
  await page.getByRole("button", { name: "Analyze ticket" }).click();
  await expect(
    page.getByRole("heading", { name: "Not enough evidence" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Approve & save note" }),
  ).toHaveCount(0);
});

test("BFF blocks cross-origin, arbitrary routes, oversized input, and credential exposure", async ({
  request,
}) => {
  const cross = await request.post("/api/sessions", {
    headers: { Origin: "https://attacker.invalid" },
    data: {},
  });
  expect(cross.status()).toBe(403);
  expect((await request.get("/api/https://attacker.invalid")).status()).toBe(
    404,
  );
  const large = await request.post("/api/sessions", {
    headers: { Origin: "http://localhost:3000" },
    data: { x: "a".repeat(5000) },
  });
  expect(large.status()).toBe(413);
  const created = await request.post("/api/sessions", {
    headers: { Origin: "http://localhost:3000" },
    data: {},
  });
  expect(created.status()).toBe(200);
  expect(await created.json()).not.toHaveProperty("token");
  expect(created.headers()["cache-control"]).toBe("no-store");
});

for (const width of [375, 768, 1440]) {
  test(`responsive static pages at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    for (const path of ["/", "/evaluations", "/workspace"]) {
      await page.goto(path);
      await expect(page.getByRole("main")).toBeVisible();
      if (path === "/evaluations")
        await page.screenshot({
          path: `${screenshotDir}/evaluations-${width}.png`,
          fullPage: true,
        });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBe(true);
    }
    await page.goto("/");
    await expect(
      page.getByText("Explore platform", { exact: false }),
    ).toHaveCount(0);
    await page.screenshot({
      path: `${screenshotDir}/landing-${width}.png`,
      fullPage: true,
    });
  });
}

for (const [sample, title, ticket] of [
  [
    "webhook",
    "Webhook retry failure",
    "Webhook delivery stopped after retries",
  ],
  [
    "credential",
    "Expired API credential",
    "API requests fail with an expired credential",
  ],
  ["export", "Expired export link", "Export download link has expired"],
]) {
  test(`scenario ${sample} opens its ticket without an AI call`, async ({
    page,
  }) => {
    const analyses: string[] = [];
    const sessions: string[] = [];
    page.on("request", (request) => {
      if (request.url().endsWith("/analyze")) analyses.push(request.url());
      if (request.url().endsWith("/api/sessions")) sessions.push(request.url());
    });
    await page.goto("/");
    await page.getByRole("link", { name: new RegExp(title) }).click();
    await expect(
      page.getByRole("heading", { name: ticket, exact: true }),
    ).toBeVisible();
    await expect(page).toHaveURL(new RegExp(`sample=${sample}`));
    expect(analyses).toHaveLength(0);
    expect(sessions).toHaveLength(1);
    await page.reload();
    await expect(
      page.getByRole("heading", { name: ticket, exact: true }),
    ).toBeVisible();
    expect(sessions).toHaveLength(1);
  });
}

for (const [code, status, message] of [
  [
    "provider_unavailable",
    503,
    "AI analysis is unavailable right now. Please try again later.",
  ],
  ["quota_exhausted", 429, "Analysis budget exhausted. Try again later."],
  [
    "session_expired",
    401,
    "Your demo session has expired. Open a new demo to continue.",
  ],
] as const) {
  test(`honest ${code} state without simulated success`, async ({ page }) => {
    await page.goto("/workspace?sample=webhook");
    await expect(
      page.getByRole("button", { name: "Analyze ticket" }),
    ).toBeVisible();
    await page.route("**/api/tickets/*/analyze", (route) =>
      route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify({ error: { code, message } }),
      }),
    );
    await page.getByRole("button", { name: "Analyze ticket" }).click();
    await expect(page.getByRole("main").getByRole("alert")).toContainText(
      message,
    );
    await expect(page.getByTestId("analysis-mode")).toHaveText("Unavailable");
    await expect(
      page.getByRole("button", { name: "Approve & save note" }),
    ).toHaveCount(0);
    if (code === "session_expired")
      await expect(
        page.getByRole("button", { name: "Open demo workspace" }),
      ).toBeVisible();
  });
}

test("configured live mode is not presented as a verified live answer", async ({
  page,
}) => {
  await page.route("**/api/tickets", async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    await route.fulfill({ response, json: { ...data, mode: "live" } });
  });
  await page.goto("/workspace?sample=webhook");
  await expect(
    page.getByRole("button", { name: "Analyze ticket" }),
  ).toBeVisible();
  await expect(page.getByTestId("analysis-mode")).toHaveText(
    "Ready for live analysis",
  );
  await expect(page.getByText("Live AI", { exact: true })).toHaveCount(0);
});

async function openTicket(page: Page) {
  await page.goto("/workspace?sample=webhook");
  await expect(
    page.getByRole("button", { name: "Analyze ticket", exact: true }),
  ).toBeVisible();
}
async function createDraft(page: Page) {
  await openTicket(page);
  await page
    .getByRole("button", { name: "Analyze ticket", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Approve & save note" }),
  ).toBeVisible();
}
async function accessible(page: Page) {
  const scan = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(scan.violations).toEqual([]);
}

test("mobile action is visible and review precedes saved notes", async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await openTicket(page);
  await expect(
    page.getByRole("button", { name: "Analyze ticket", exact: true }),
  ).toBeInViewport();
  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.screenshot({
      path: `${screenshotDir}/workspace-ready-${width}.png`,
      fullPage: true,
    });
  }
  await page.setViewportSize({ width: 375, height: 812 });
  await page
    .getByRole("button", { name: "Analyze ticket", exact: true })
    .click();
  const draft = page.getByRole("heading", { name: "Review the internal note" });
  const saved = page.getByRole("heading", { name: "Saved internal notes" });
  await expect(
    page.getByRole("button", { name: "Approve & save note" }),
  ).toBeVisible();
  const order = await page.evaluate(() =>
    document
      .querySelector("#proposal-title")!
      .compareDocumentPosition(document.querySelector("#saved-notes-title")!),
  );
  expect(order & 4).toBe(4);
  expect((await draft.boundingBox())!.y).toBeLessThan(
    (await saved.boundingBox())!.y,
  );
  await page
    .getByRole("link", { name: /Review the proposed note/ })
    .press("Enter");
  await expect(draft).toBeFocused();
  await expect(draft).toBeInViewport();
});

test("keyboard-only analysis, source dialog, rejection and navigation", async ({
  page,
}) => {
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to content" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await page
    .getByRole("link", { name: /Webhook retry failure/ })
    .press("Enter");
  await page
    .getByRole("button", { name: "Analyze ticket", exact: true })
    .press("Enter");
  await expect(
    page.getByRole("heading", { name: "AI suggestion", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Tab");
  const sourceButton = page.getByRole("button", { name: /View source/ });
  await expect(sourceButton).toBeFocused();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("Original excerpt");
  for (let index = 0; index < 8; index++) {
    await page.keyboard.press("Tab");
    expect(
      await page.evaluate(() => !!document.activeElement?.closest("dialog")),
    ).toBe(true);
  }
  await page.keyboard.press("Escape");
  await expect(sourceButton).toBeFocused();
  await page.getByRole("button", { name: "Reject draft" }).press("Enter");
  await expect(page.getByRole("status")).toBeFocused();
  await page.reload();
  await expect(page.getByRole("status")).toContainText(
    "Draft rejected. No note saved.",
  );
  await expect(page.locator(".saved-note")).toHaveCount(0);
  await page
    .getByRole("link", { name: "Sample tickets", exact: true })
    .press("Enter");
  await expect(
    page.getByRole("link", { name: "Sample tickets", exact: true }),
  ).toHaveAttribute("aria-current", "page");
});

test("analysis and source loading have distinct accessible states", async ({
  page,
}) => {
  await openTicket(page);
  let releaseAnalysis!: () => void;
  const analysisGate = new Promise<void>((resolve) => {
    releaseAnalysis = resolve;
  });
  await page.route("**/api/tickets/*/analyze", async (route) => {
    await analysisGate;
    await route.continue();
  });
  await page
    .getByRole("button", { name: "Analyze ticket", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Analyzing ticket…" }),
  ).toBeDisabled();
  await expect(page.getByRole("status")).toContainText("Finding documentation");
  await page.screenshot({
    path: `${screenshotDir}/analysis-loading.png`,
    fullPage: true,
  });
  releaseAnalysis();
  await expect(
    page.getByRole("button", { name: "Approve & save note" }),
  ).toBeVisible();
  let releaseSource!: () => void;
  const sourceGate = new Promise<void>((resolve) => {
    releaseSource = resolve;
  });
  await page.route("**/api/runs/*/sources/*", async (route) => {
    await sourceGate;
    await route.continue();
  });
  await page.getByRole("button", { name: /View source/ }).click();
  await expect(page.getByRole("dialog").getByRole("status")).toContainText(
    "Loading the original passage",
  );
  await expect(
    page.getByRole("button", { name: "Analyzing ticket…" }),
  ).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: /View source/ })).toBeFocused();
  releaseSource();
  await expect(
    page.getByRole("button", { name: "Analyze ticket", exact: true }),
  ).toBeEnabled();
  await expect(page.getByRole("dialog")).not.toBeVisible();
});

test("failed source loads recover in the drawer and preserve the draft", async ({
  page,
}) => {
  await createDraft(page);
  const draft = await page.locator(".proposed-note").innerText();
  await page.route("**/api/runs/*/sources/*", (route) => route.abort());
  await page.getByRole("button", { name: /View source/ }).click();
  await expect(page.getByRole("dialog").getByRole("alert")).toContainText(
    "source could not be loaded",
  );
  await page.unroute("**/api/runs/*/sources/*");
  await page.getByRole("button", { name: "Try loading source again" }).click();
  await expect(page.getByRole("dialog")).toContainText(
    "Webhook retry schedule",
  );
  await page.keyboard.press("Escape");
  await expect(page.locator(".proposed-note")).toHaveText(draft);
  await expect(page.getByTestId("analysis-mode")).not.toHaveText("Unavailable");
});

test("lost approval response recovers the exact saved note without a second decision", async ({
  page,
}) => {
  await createDraft(page);
  const draft = await page.locator(".proposed-note").innerText();
  let decisions = 0;
  await page.route("**/api/proposals/*/decision", async (route) => {
    decisions++;
    const response = await route.fetch();
    expect(response.ok()).toBe(true);
    await route.abort();
  });
  await page.getByRole("button", { name: "Approve & save note" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "could not confirm the result",
  );
  await expect(page.locator(".proposed-note")).toHaveText(draft);
  await expect(
    page.getByText("Note approved and saved", { exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Refresh ticket" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Note approved and saved",
  );
  await expect(page.locator(".saved-note blockquote")).toHaveText(draft);
  expect(decisions).toBe(1);
});

test("draft expiry while open removes decision controls", async ({ page }) => {
  await page.clock.install();
  await page.route("**/api/runs/*", async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    if (data.proposal)
      data.proposal.expires_at = new Date(Date.now() + 5000).toISOString();
    await route.fulfill({ response, json: data });
  });
  await createDraft(page);
  await page.clock.fastForward(6000);
  await expect(
    page.getByText("New analysis needed", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Approve & save note" }),
  ).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Reject draft" })).toHaveCount(
    0,
  );
  await expect(
    page.getByRole("link", { name: /Back to analysis/ }),
  ).toBeVisible();
});

test("failed reanalysis does not show the previous draft as a new result", async ({
  page,
}) => {
  await createDraft(page);
  await page.route("**/api/tickets/*/analyze", (route) =>
    route.fulfill({
      status: 429,
      json: {
        error: {
          code: "quota_exhausted",
          message: "Analysis budget exhausted. Try again later.",
        },
      },
    }),
  );
  await page
    .getByRole("button", { name: "Analyze ticket", exact: true })
    .click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "budget exhausted",
  );
  await expect(
    page.getByRole("button", { name: "Approve & save note" }),
  ).toHaveCount(0);
  await expect(page.getByText("No new suggestion to review")).toBeVisible();
  await page.screenshot({
    path: `${screenshotDir}/analysis-error.png`,
    fullPage: true,
  });
});

test("all three pages and review states pass automated accessibility checks", async ({
  page,
}) => {
  for (const path of ["/", "/evaluations", "/workspace"]) {
    await page.goto(path);
    await accessible(page);
  }
  await createDraft(page);
  await accessible(page);
  await page.setViewportSize({ width: 375, height: 812 });
  await accessible(page);
  await page.getByRole("button", { name: /View source/ }).click();
  await expect(page.getByRole("dialog")).toContainText("Original excerpt");
  await accessible(page);
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Approve & save note" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Note approved and saved",
  );
  await accessible(page);
});

test("320px reflow and reduced motion keep navigation and controls usable", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 900 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const path of ["/", "/evaluations", "/workspace?sample=webhook"]) {
    await page.goto(path);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    const current = page
      .getByRole("navigation")
      .locator('[aria-current="page"]');
    await expect(current).toHaveCount(1);
    await expect(current).toBeVisible();
  }
  const analysis = page.getByRole("button", {
    name: "Analyze ticket",
    exact: true,
  });
  await expect(analysis).toBeEnabled();
  expect((await analysis.boundingBox())!.height).toBeGreaterThanOrEqual(44);
});
