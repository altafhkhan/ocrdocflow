// Everything that differs between the website and the Android/iOS apps
// (the same React code packaged with Capacitor) goes through this file.
// Setup and release steps: deploy/MOBILE.md.
import { Capacitor } from "@capacitor/core";

/** True inside the Android or iOS app, false in any browser. */
export const isNativeApp = Capacitor.isNativePlatform();

/** The website. The apps send people here to buy or change a plan. */
export const WEBSITE_URL = "https://ocrdocflow.qumaxa.com";

/**
 * Where the API lives. The website calls its own origin (nginx proxies
 * /api); a packaged app has no such origin, so it always calls the live
 * server by its full address.
 */
export function apiBase(): string {
  if (isNativeApp) return import.meta.env.VITE_MOBILE_API_BASE_URL ?? WEBSITE_URL;
  return import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
}

/** Opens a page in the phone's own browser (or a new tab on the web). */
export function openExternal(url: string) {
  // Inside the app, leaving for another site hands the address to the
  // phone's browser; the app itself stays where it was.
  if (isNativeApp) window.location.href = url;
  else window.open(url, "_blank", "noopener");
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Could not read the file."));
    reader.onload = () => resolve(String(reader.result).split(",")[1] ?? "");
    reader.readAsDataURL(blob);
  });
}

/**
 * Hands a generated file (CSV / Excel export) to the user.
 *
 * Browser: the usual download. App: a download link does nothing inside a
 * WebView, so the file is written to the app's cache and the phone's share
 * sheet opens - from there the user saves it to Files/Drive, emails it or
 * opens it in Excel.
 */
export async function saveBlob(blob: Blob, filename: string) {
  if (!isNativeApp) {
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
    return;
  }

  const { Filesystem, Directory } = await import("@capacitor/filesystem");
  const { Share } = await import("@capacitor/share");
  const written = await Filesystem.writeFile({
    path: filename.replace(/[\\/:*?"<>|]/g, "_"),
    data: await blobToBase64(blob),
    directory: Directory.Cache,
  });
  try {
    await Share.share({ title: filename, files: [written.uri] });
  } catch (err: any) {
    // Closing the share sheet without picking anything is not an error.
    if (!/cancel/i.test(String(err?.message ?? err))) throw err;
  }
}

/**
 * Phone cameras produce photos larger than the 10 MB upload limit, and big
 * photos are slow to send. Shrinks a photo so its long side is at most
 * 2500 px (plenty for OCR) and re-saves it as JPEG. Returns the original
 * file if it is already small or cannot be decoded.
 */
export async function shrinkPhoto(file: File): Promise<File> {
  const MAX_SIDE = 2500;
  if (!file.type.startsWith("image/")) return file;
  try {
    const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
    const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
    if (scale === 1 && file.size <= 3 * 1024 * 1024) return file;
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    canvas.getContext("2d")!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.85));
    if (!blob) return file;
    return new File([blob], file.name.replace(/\.[^.]+$/, "") + ".jpg", { type: "image/jpeg" });
  } catch {
    return file;
  }
}
