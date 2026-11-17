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

export default config;
