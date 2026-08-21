// @ts-check
import { defineConfig } from "astro/config";
import tailwind from "@tailwindcss/vite";

export default defineConfig({
  site: "https://chasecmathis.github.io",
  // GitHub Pages project site. Every internal link goes through url() in
  // src/lib/url.ts so this stays the only place the prefix is written.
  base: "/ff-newsletter",
  trailingSlash: "always",
  vite: { plugins: [tailwind()] },
});
