import { resolve } from "node:path";
import { defineConfig, type Plugin } from "vitest/config";

const page = (path: string): string => resolve(import.meta.dirname, path);

// GitHub Pages cannot send headers, so the built pages carry their policy in a meta tag. The dev
// server is left without it because it injects styles inline.
const CSP =
  "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; " +
  "base-uri 'none'; form-action 'none'; object-src 'none'";

function contentSecurityPolicy(): Plugin {
  return {
    name: "owl-content-security-policy",
    apply: "build",
    transformIndexHtml: () => [
      { tag: "meta", attrs: { "http-equiv": "Content-Security-Policy", content: CSP }, injectTo: "head-prepend" },
    ],
  };
}

// A relative base keeps every link working wherever the site is served, so a fork needs no change.
export default defineConfig({
  base: "./",
  plugins: [contentSecurityPolicy()],
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
