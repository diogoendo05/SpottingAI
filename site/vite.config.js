import { defineConfig } from "vite";

export default defineConfig({
  base: "/",
  build: {
    target: "es2022",
    // O GLB e as fontes vão como arquivos com hash, nunca embutidos no JS.
    assetsInlineLimit: 0,
  },
});
