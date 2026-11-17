import type { CapacitorConfig } from "@capacitor/cli";

// Wraps the built web app (frontend/dist) as the Android and iOS apps.
// Setup and release steps: deploy/MOBILE.md.
const config: CapacitorConfig = {
  appId: "com.qumaxa.ocrdocflow",
  appName: "OCRDocFlow",
  webDir: "dist",
  ios: {
    // Keeps the page clear of the notch and the home bar.
    contentInset: "automatic",
  },
};

// Development only: `CAP_DEV_SERVER=http://localhost:5173 npx cap sync`
// makes the app load its pages from the running dev server instead of the
// copy packed inside it (see "Testing against the local server" in
// deploy/MOBILE.md). Never set this for a build that goes to a store.
if (process.env.CAP_DEV_SERVER) {
  config.server = { url: process.env.CAP_DEV_SERVER, cleartext: true };
}

export default config;
