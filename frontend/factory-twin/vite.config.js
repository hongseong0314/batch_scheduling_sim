import { fileURLToPath, URL } from "node:url";

import { defineConfig } from "vite";

export default defineConfig({
  build: {
    emptyOutDir: true,
    lib: {
      entry: fileURLToPath(new URL("./src/main.js", import.meta.url)),
      formats: ["es"],
      fileName: () => "factory-twin.js",
    },
    outDir: fileURLToPath(
      new URL("../../src/mes/ui/static/dist", import.meta.url),
    ),
    sourcemap: true,
  },
});
