import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: resolve(__dirname, "../app/ui/static/island"),
    emptyOutDir: true,
    manifest: false,
    // No source maps: the bundle ships as-is and the TSX sources are in the repo,
    // so shipping a second copy of them to every browser buys nothing.
    sourcemap: false,
    // Emit ONE shared CSS bundle (style.css) for all entries. base.html
    // links it once via <link href="/static/island/style.css">. Default
    // (true) splits CSS per chunk and names the file after whichever shared
    // chunk imports the global stylesheet (e.g. LiveRegion.css), which
    // breaks the deterministic link path Jinja needs.
    cssCodeSplit: false,
    rollupOptions: {
      // One entry, because there is one interactive page. The entry form is
      // plain HTML and mounts no island at all.
      input: {
        app: resolve(__dirname, "src/app.tsx"),
      },
      output: {
        entryFileNames: "[name].js",
        assetFileNames: "[name][extname]",
        chunkFileNames: "chunks/[name]-[hash].js",
      },
    },
  },
});
