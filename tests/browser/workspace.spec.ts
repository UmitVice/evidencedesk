import { test, expect, type Page } from "@playwright/test";

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
  await page.getByRole("link", { name: "Investigate a sample ticket" }).click();
  await expect(
    page.getByRole("heading", {
      name: "Webhook delivery stopped after retries",
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Analyze ticket" }).click();
  await expect(
    page.getByRole("button", { name: "Approve and add note" }),
  ).toBeVisible();
  await page.getByRole("button", { name: /Inspect evidence/ }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("dialog")).toContainText(
    "Webhook retry schedule",
  );
  await expect(page.getByRole("dialog")).toContainText("Claim under review");
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
      path: `docs/screenshots/evidence-${width}.png`,
      fullPage: false,
    });
  }
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: /Inspect evidence/ }),
  ).toBeFocused();
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Approve and add note" }),
  ).toBeVisible();
  for (const width of [375, 768]) {
    await page.setViewportSize({ width, height: 900 });
    const approve = page.getByRole("button", { name: "Approve and add note" });
    await approve.scrollIntoViewIfNeeded();
    await expect(approve).toBeInViewport();
    await page.screenshot({
      path: `docs/screenshots/workspace-${width}.png`,
      fullPage: true,
    });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole("button", { name: "Approve and add note" }).click();
  await expect(page.getByRole("status")).toHaveText(
    "The exact approved note is saved.",
  );
  await page.reload();
  await expect(page.getByRole("status")).toHaveText(
    "The exact approved note is saved.",
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
    path: "docs/screenshots/workspace.png",
    fullPage: true,
  });
});

test("rejection and insufficient evidence do not create notes", async ({
  page,
}) => {
  await page.goto("/workspace");
  await page.getByRole("button", { name: "Start sandbox session" }).click();
  await page.getByRole("button", { name: "Analyze ticket" }).click();
  await page
    .getByRole("button", { name: "Reject proposal", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText("Rejected");
  await expect(
    page.getByText("No notes saved.", { exact: false }),
  ).toBeVisible();
  await page
    .getByLabel("Optional question")
    .selectOption("Can RelayNest configure SSO?");
  await page.getByRole("button", { name: "Analyze ticket" }).click();
  await expect(
    page.getByRole("heading", { name: "Insufficient evidence" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Approve and add note" }),
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
          path: `docs/screenshots/evaluations-${width}.png`,
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
      path: `docs/screenshots/landing-${width}.png`,
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
  ["export", "Export processing issue", "Export download link has expired"],
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
  ["provider_unavailable", 503, "Live AI is not configured."],
  ["quota_exhausted", 429, "Analysis budget exhausted. Try again later."],
  ["session_expired", 401, "Start a new sandbox session."],
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
      page.getByRole("button", { name: "Approve and add note" }),
    ).toHaveCount(0);
    if (code === "session_expired")
      await expect(
        page.getByRole("button", { name: "Start sandbox session" }),
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
