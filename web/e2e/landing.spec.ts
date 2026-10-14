import { expect, test } from "@playwright/test";

test("landing page links to setup", async ({ page }) => {
  await page.goto("./");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Your music, one turn away.");
  await page.getByRole("link", { name: "Set up your owl" }).first().click();
  await expect(page.getByRole("heading", { name: "Set up your owl" })).toBeVisible();
});

test("the volume ring turns with the keyboard and stops at the ends", async ({ page }) => {
  await page.goto("./");
  const ring = page.getByRole("slider", { name: "Volume" });
  await ring.focus();
  await page.keyboard.press("ArrowUp");
  await expect(ring).toHaveAttribute("aria-valuenow", "64");
  await page.keyboard.press("End");
  await page.keyboard.press("ArrowUp");
  await expect(ring).toHaveAttribute("aria-valuenow", "100");
  await page.keyboard.press("Home");
  await expect(ring).toHaveAttribute("aria-valuenow", "0");
  await expect(page.locator("#ring-value")).toHaveText("0");
});

test("the volume ring turns with the mouse wheel", async ({ page }) => {
  await page.goto("./");
  const ring = page.getByRole("slider", { name: "Volume" });
  await ring.scrollIntoViewIfNeeded();
  await ring.hover();
  await page.mouse.wheel(0, -100);
  await expect(ring).toHaveAttribute("aria-valuenow", "64");
});
