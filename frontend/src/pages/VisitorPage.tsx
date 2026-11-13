import { useEffect, useRef, useState } from "react";
import { UPLOAD_LANGUAGES } from "../languages";
import { useNavigate } from "react-router-dom";
import UploadDropZone from "../components/UploadDropZone";
import {
  visitorUpload, listVisitorDocuments, getVisitorExtraction, downloadVisitorCsv,
} from "../api";

interface DocRow {
  id: number;
  original_filename: string;
  status: string;
  language: string;
  uploaded_at: string;
}

const STATUS_STYLES: Record<string, string> = {
  uploaded: "bg-gray-100 text-gray-700",
  processing: "bg-yellow-100 text-yellow-800",
  done: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

export default function VisitorPage() {
  const [docs, setDocs] = useState<DocRow[]>([]);
  const [language, setLanguage] = useState("auto");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadsRemaining, setUploadsRemaining] = useState<number | null>(null);

  // Email-gate state: when the backend says EMAIL_REQUIRED, we hold the
  // pending file/language and show an email prompt instead of losing
  // what the visitor was trying to upload.
  const [needsEmail, setNeedsEmail] = useState(false);
  const [emailInput, setEmailInput] = useState("");
  const pendingFileRef = useRef<File | null>(null);

  const [viewingExtraction, setViewingExtraction] = useState<any>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    refreshList();
  }, []);

  async function refreshList() {
    try {
      const data = await listVisitorDocuments();
      setDocs(data);
    } catch {
      // Fine to ignore on first load - visitor may have no docs yet.
    }
  }

  async function doUpload(file: File, email?: string) {
    setUploading(true);
    setError("");
    setMessage("");
    try {
      const result = await visitorUpload(file, language, email);
      setMessage("Done! See your results below.");
      setUploadsRemaining(result.uploads_remaining);
      setNeedsEmail(false);
      pendingFileRef.current = null;
      refreshList();
    } catch (err: any) {
      if (err.message === "EMAIL_REQUIRED") {
        pendingFileRef.current = file;
        setNeedsEmail(true);
      } else {
        setError(err.message);
      }
    } finally {
      setUploading(false);
    }
  }

  // One path for a file picked in the dialog and a file dropped on the box.
  async function handleFile(file: File) {
    await doUpload(file);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  async function handleEmailSubmit() {
    if (!emailInput.includes("@")) {
      setError("Please enter a valid email address.");
      return;
    }
    if (pendingFileRef.current) {
      await doUpload(pendingFileRef.current, emailInput);
    }
  }

  async function handleView(docId: number) {
    setError("");
    try {
      const data = await getVisitorExtraction(docId);
      setViewingExtraction(data);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function handleDownloadCsv() {
    setError("");
    try {
      await downloadVisitorCsv(language);
    } catch (err: any) {
      setError(err.message);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-3xl mx-auto">
        <div className="flex justify-between items-center mb-2">
          <h1 className="text-2xl font-bold">OCRDocFlow — Try it free</h1>
          <div className="flex gap-3">
            <button onClick={() => navigate("/login")} className="text-sm text-gray-600 hover:underline">
              Log in
            </button>
            <button
              onClick={() => navigate("/register")}
              className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded hover:bg-blue-700"
            >
              Sign up free
            </button>
          </div>
        </div>
        <p className="text-sm text-gray-500 mb-6">
          Upload an invoice and see it read automatically - no account needed.
          {uploadsRemaining !== null && (
            <span className="ml-1">({uploadsRemaining} free {uploadsRemaining === 1 ? "upload" : "uploads"} left)</span>
          )}
        </p>

        <div className="bg-white rounded-lg shadow p-4 mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Document language
          </label>
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="border rounded px-3 py-2 mb-4 w-full"
            disabled={uploading}
          >
            {UPLOAD_LANGUAGES.map((l) => (
              <option key={l.code} value={l.code}>{l.label}</option>
            ))}
          </select>

          <UploadDropZone
            inputRef={fileInputRef}
            disabled={uploading || needsEmail}
            busy={uploading}
            idleText="Drag and drop a PDF or image invoice here, or click to choose a file (max 1 MB)"
            onFile={handleFile}
            onReject={setError}
          />
        </div>

        {needsEmail && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4">
            <p className="text-sm text-amber-800 mb-2">
              You've used your first 5 free uploads! Enter your email to keep going for free,
              and we'll send you occasional plan info (no spam).
            </p>
            <div className="flex gap-2">
              <input
                type="email"
                value={emailInput}
                onChange={(e) => setEmailInput(e.target.value)}
                placeholder="you@example.com"
                className="flex-1 border rounded px-3 py-2 text-sm"
              />
              <button
                onClick={handleEmailSubmit}
                disabled={uploading}
                className="px-4 py-2 rounded bg-blue-600 text-white hover:bg-blue-700 text-sm disabled:opacity-50"
              >
                Continue
              </button>
            </div>
          </div>
        )}

        {message && <p className="text-sm text-blue-700 mb-4">{message}</p>}
        {error && <p className="text-sm text-red-600 mb-4">{error}</p>}

        <div className="bg-white rounded-lg shadow overflow-hidden mb-4">
          <div className="p-4 flex justify-between items-center border-b">
            <span className="font-semibold text-gray-800">Your Uploads ({docs.length})</span>
            {docs.length > 0 && (
              <button onClick={handleDownloadCsv} className="text-sm text-blue-600 hover:underline">
                Download CSV
              </button>
            )}
          </div>
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-100">
              <tr>
                <th className="p-3">File</th>
                <th className="p-3">Status</th>
                <th className="p-3">Uploaded</th>
                <th className="p-3"></th>
              </tr>
            </thead>
            <tbody>
              {docs.map((d) => (
                <tr key={d.id} className="border-t text-sm">
                  <td className="p-3">{d.original_filename}</td>
                  <td className="p-3">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${STATUS_STYLES[d.status] || ""}`}>
                      {d.status}
                    </span>
                  </td>
                  <td className="p-3">{new Date(d.uploaded_at).toLocaleString()}</td>
                  <td className="p-3">
                    {d.status === "done" && (
                      <button onClick={() => handleView(d.id)} className="text-blue-600 hover:underline text-xs">
                        View
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {docs.length === 0 && (
                <tr>
                  <td colSpan={4} className="p-3 text-center text-gray-400">
                    No uploads yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-900">
          Want to edit extracted data, save invoices permanently, and export unlimited reports?{" "}
          <button onClick={() => navigate("/register")} className="font-semibold underline">
            Create a free account
          </button>
        </div>
      </div>

      {viewingExtraction && (
        <div
          className="fixed inset-0 bg-black/40 flex items-center justify-center p-4"
          onClick={() => setViewingExtraction(null)}
        >
          <div
            className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] overflow-y-auto p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-start mb-4">
              <h2 className="font-bold text-lg">Extracted Data (preview only)</h2>
              <button onClick={() => setViewingExtraction(null)} className="text-gray-400 hover:text-gray-700">
                ✕
              </button>
            </div>
            <p className="text-xs text-gray-500 mb-3">
              Sign up to edit and save this data permanently.
            </p>
            <div className="grid grid-cols-2 gap-2 text-sm mb-4">
              <div><span className="text-gray-500">Invoice Number:</span> {viewingExtraction.invoice_number || "—"}</div>
              <div><span className="text-gray-500">Invoice Date:</span> {viewingExtraction.invoice_date || "—"}</div>
              <div><span className="text-gray-500">Client Name:</span> {viewingExtraction.client_name || "—"}</div>
              <div><span className="text-gray-500">Grand Total:</span> {viewingExtraction.grand_total ?? "—"}</div>
            </div>
            <table className="w-full text-sm">
              <thead className="text-left text-gray-500">
                <tr><th>Description</th><th>Qty</th><th>Unit Price</th><th>Total</th></tr>
              </thead>
              <tbody>
                {viewingExtraction.items.map((item: any, i: number) => (
                  <tr key={i} className="border-t">
                    <td className="py-1">{item.description || "—"}</td>
                    <td className="py-1">{item.qty ?? "—"}</td>
                    <td className="py-1">{item.unit_price ?? "—"}</td>
                    <td className="py-1">{item.total_price ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
