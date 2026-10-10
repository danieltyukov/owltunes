import { defineConfig, devices } from "@playwright/test";

// The built site is served under /owltunes/, the path GitHub Pages uses, to prove relative links work.
export default defineConfig({
  testDir: "e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://127.0.0.1:4173/owltunes/",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run build && npx vite preview --strictPort --port 4173 --base /owltunes/",
    url: "http://127.0.0.1:4173/owltunes/",
    reuseExistingServer: !process.env.CI,
  },
});
