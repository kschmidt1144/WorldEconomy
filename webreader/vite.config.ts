import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { VitePWA } from "vite-plugin-pwa";

// Served at kykli.dev/worldeconomy in prod; root in local dev.
const BASE = "/worldeconomy/";

export default defineConfig({
  base: BASE,
  plugins: [
    vue(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icon.svg"],
      manifest: {
        name: "World Economy Lab — Reader",
        short_name: "Econ Reader",
        description: "Read the World Economy Lab report and take margin notes, offline.",
        theme_color: "#0d3b4f",
        background_color: "#f6f4ee",
        display: "standalone",
        orientation: "any",
        start_url: BASE,
        scope: BASE,
        icons: [
          { src: "icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any maskable" },
        ],
      },
      workbox: {
        // App shell + chapter markdown are small -> precache. Figures are ~21MB -> cache on first view.
        globPatterns: ["**/*.{js,css,html,svg,woff2}", "report/*.md", "report/manifest.json"],
        maximumFileSizeToCacheInBytes: 6 * 1024 * 1024,
        runtimeCaching: [
          {
            urlPattern: ({ url }) => url.pathname.includes("/report/figures/"),
            handler: "CacheFirst",
            options: {
              cacheName: "report-figures",
              expiration: { maxEntries: 200, maxAgeSeconds: 60 * 60 * 24 * 90 },
            },
          },
        ],
      },
      devOptions: { enabled: false },
    }),
  ],
});
