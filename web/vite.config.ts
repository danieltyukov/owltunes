import { resolve } from "node:path";
import { defineConfig } from "vitest/config";

const page = (path: string): string => resolve(import.meta.dirname, path);

// A relative base keeps every link working wherever the site is served, so a fork needs no change.
export default defineConfig({
  base: "./",
  build: {
    rollupOptions: {
      input: {
        home: page("index.html"),
        setup: page("setup/index.html"),
        callback: page("callback/index.html"),
      },
    },
  },
  test: {
    environment: "jsdom",
    include: ["tests/**/*.test.ts"],
  },
});
