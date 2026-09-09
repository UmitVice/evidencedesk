import { test, expect } from "@playwright/test";

test("source inspection, pending reload, approval and persisted note", async ({
  page,
  context,
}) => {
  await page.goto("/workspace");
  await page.getByRole("button", { name: "Start sandbox session" }).click();
  await page.getByRole("button", { name: /webhook.*Webhook delivery/ }).click();
  await page.getByRole("button", { name: "Analyze ticket" }).click();
  await expect(
    page.getByRole("button", { name: "Approve note" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: /Inspect supporting excerpt/ })
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("dialog")).toContainText(
    "Webhook retry schedule",
  );
  await page.keyboard.press("Escape");
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Approve note" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Approve note" }).click();
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
  await page.getByRole("button", { name: "Reject", exact: true }).click();
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
  await expect(page.getByRole("button", { name: "Approve note" })).toHaveCount(
    0,
  );
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
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBe(true);
    }
    await page.goto("/");
    await page.screenshot({
      path: `docs/screenshots/landing-${width}.png`,
      fullPage: true,
    });
  });
}
