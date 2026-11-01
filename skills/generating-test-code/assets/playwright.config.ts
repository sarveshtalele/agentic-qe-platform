// Template: copy to the project root as playwright.config.ts for every generated UI suite.
// A plain object keeps it dependency-free; Playwright accepts it as the default export.
export default {
  testDir: "tests",
  retries: 0,
  use: {
    baseURL: process.env.BASE_URL,
    screenshot: "on", // every case leaves evidence; collect-evidence.ts copies it to docs/qe/<app>/06-execution/evidence/e2e
    trace: "retain-on-failure",
    video: "off"
  },
  reporter: [
    ["list"],
    ["junit", { outputFile: "results/junit.xml" }],
    ["json", { outputFile: "results/playwright.json" }],
    ["html", { outputFolder: "playwright-report", open: "never" }]
  ],
  outputDir: "test-results",
  projects: [{ name: "chromium", use: { browserName: "chromium" } }]
};
