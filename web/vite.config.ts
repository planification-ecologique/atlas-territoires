import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// `base` relatif : l'application est un site statique déployable n'importe où
// (GitHub Pages, serveur de fichiers d'une administration...).
export default defineConfig({
  base: "./",
  plugins: [react()],
});
