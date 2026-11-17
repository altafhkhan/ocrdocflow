import { useEffect, useRef, useState } from "react";

interface Props {
  /** Address of the PDF (a blob: URL made from the downloaded file). */
  url: string;
  unavailableText: string;
}

/**
 * Draws every page of a PDF as a picture, one under the other.
 *
 * Used only inside the Android/iOS apps, where the WebView has no PDF
 * viewer of its own (a browser just shows the PDF in a frame). The PDF
 * library is loaded on demand so the website does not download it.
 */
export default function PdfPages({ url, unavailableText }: Props) {
  const holder = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const box = holder.current;
    setFailed(false);

    (async () => {
      // The "legacy" build runs on the older WebViews still found on Android phones.
      const pdfjs = await import("pdfjs-dist/legacy/build/pdf.mjs");
      const worker = await import("pdfjs-dist/legacy/build/pdf.worker.min.mjs?url");
      pdfjs.GlobalWorkerOptions.workerSrc = worker.default;

      const data = await (await fetch(url)).arrayBuffer();
      const pdf = await pdfjs.getDocument({ data }).promise;
      if (!box) return;
      const width = box.clientWidth || 360;
      const sharpness = Math.min(window.devicePixelRatio || 1, 2);

      for (let n = 1; n <= pdf.numPages && !cancelled; n++) {
        const page = await pdf.getPage(n);
        const fit = width / page.getViewport({ scale: 1 }).width;
        const viewport = page.getViewport({ scale: fit * sharpness });
        const canvas = document.createElement("canvas");
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        canvas.className = "block w-full h-auto mb-2 bg-white";
        await page.render({ canvasContext: canvas.getContext("2d")!, viewport }).promise;
        if (!cancelled) box.appendChild(canvas);
      }
    })().catch(() => {
      if (!cancelled) setFailed(true);
    });

    return () => {
      cancelled = true;
      if (box) box.replaceChildren();
    };
  }, [url]);

  return (
    <div className="w-full">
      {failed && <p className="text-sm text-gray-500 p-4">{unavailableText}</p>}
      <div ref={holder} className="w-full" />
    </div>
  );
}
