import { useEffect, useRef, useState } from "react";
import { UPLOAD_LANGUAGES } from "../languages";
import { uploadDocument, listDocuments, getDocument, getToken, getMe, confirmCheckout, CurrentUser } from "../api";
import { useNavigate } from "react-router-dom";
import UploadDropZone from "../components/UploadDropZone";
import ReviewModal from "../components/ReviewModal";
import ExportPanel from "../components/ExportPanel";

interface DocRow {
  id: number;
  original_filename: string;
  status: string;
  uploaded_at: string;
  language: string;
  detected_language: string | null;
}

interface DocDetail extends DocRow {
  ocr_text: string | null;
  page_count: number | null;
  error_message: string | null;
}

const STATUS_STYLES: Record<string, string> = {
  uploaded: "bg-gray-100 text-gray-700",
  processing: "bg-yellow-100 text-yellow-800",
  done: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

const UPLOAD_STAGES = [
  { label: "Uploading file...", percent: 20 },
  { label: "Reading document (OCR)...", percent: 65 },
  { label: "Saving results...", percent: 90 },
];

export default function Dashboard() {
  const [docs, setDocs] = useState<DocRow[]>([]);
  const [language, setLanguage] = useState("auto");
  const [message, setMessage] = useState("");
  const [uploading, setUploading] = useState(false);
  const [stageIndex, setStageIndex] = useState(0);
  const [historyOpen, setHistoryOpen] = useState(true);
  const [viewingDoc, setViewingDoc] = useState<DocDetail | null>(null);
  const [reviewingDocId, setReviewingDocId] = useState<number | null>(null);
  const [reviewingLanguage, setReviewingLanguage] = useState<string>("en");
  const [lastFile, setLastFile] = useState<File | null>(null);
  const [lastDetectedLanguage, setLastDetectedLanguage] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [checkoutNotice, setCheckoutNotice] = useState<{ ok: boolean; text: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const stageTimerRef = useRef<number | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!getToken()) {
      navigate("/login");
      return;
    }
    refreshList();

    // Back from Stripe Checkout? Confirm the payment BEFORE reading the
    // account, so the plan shown is the one just bought. The query string
    // is removed either way, so a refresh does not repeat this.
    const params = new URLSearchParams(window.location.search);
    const checkout = params.get("checkout");
    const sessionId = params.get("session_id");
    if (checkout) window.history.replaceState(null, "", window.location.pathname);
    if (checkout === "success" && sessionId) {
      setCheckoutNotice({ ok: true, text: "Confirming your payment..." });
      confirmCheckout(sessionId)
        .then((r) => setCheckoutNotice({ ok: r.status === "active", text: r.message }))
        .catch((err) => setCheckoutNotice({ ok: false, text: err.message }))
        .finally(() => getMe().then(setCurrentUser).catch(() => {}));
    } else {
      if (checkout === "cancelled") setCheckoutNotice({ ok: false, text: "Checkout was cancelled. Your plan has not changed." });
      getMe().then(setCurrentUser).catch(() => {});
    }
    return () => {
      if (stageTimerRef.current) window.clearInterval(stageTimerRef.current);
    };
  }, []);

  async function refreshList() {
    try {
      const data = await listDocuments();
      setDocs(data);
    } catch (err: any) {
      setMessage(err.message);
    }
  }

  function startStageAnimation() {
    setStageIndex(0);
    let i = 0;
    stageTimerRef.current = window.setInterval(() => {
      i = Math.min(i + 1, UPLOAD_STAGES.length - 1);
      setStageIndex(i);
    }, 1200);
  }

  function stopStageAnimation() {
    if (stageTimerRef.current) {
      window.clearInterval(stageTimerRef.current);
      stageTimerRef.current = null;
    }
  }

  async function doUpload(file: File) {
    setUploading(true);
    setMessage("");
    startStageAnimation();
    try {
      const result = await uploadDocument(file, language);
      setMessage("Done! Check Upload History below for the result.");
      refreshList();
      try {
        const detail = await getDocument(result.id);
        setLastDetectedLanguage(detail.detected_language ?? null);
      } catch {
        setLastDetectedLanguage(null);
      }
    } catch (err: any) {
      setMessage(err.message);
    } finally {
      stopStageAnimation();
      setUploading(false);
    }
  }

  // One path for a file picked in the dialog and a file dropped on the box.
  async function handleFile(file: File) {
    setLastFile(file);
    await doUpload(file);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  async function handleRetryWithDifferentLanguage() {
    if (!lastFile) return;
    await doUpload(lastFile);
  }

  async function openDocument(id: number) {
    try {
      const doc = await getDocument(id);
      setViewingDoc(doc);
    } catch (err: any) {
      setMessage(err.message);
    }
  }

  function logout() {
    localStorage.removeItem("token");
    navigate("/login");
  }

  const currentStage = UPLOAD_STAGES[stageIndex];

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-3xl mx-auto">
        <div className="flex justify-between items-center mb-2">
          <div>
            <h1 className="text-2xl font-bold">Your Documents</h1>
            {currentUser && (
              <p className="text-sm text-gray-500 mt-1">
                {currentUser.full_name || currentUser.email}
                {" · "}
                <span className="capitalize font-medium">{currentUser.plan}</span> plan
                {currentUser.role === "admin" && (
                  <span className="ml-1 text-purple-600 font-medium">(Admin)</span>
                )}
                {currentUser.role !== "admin" &&
  typeof currentUser.invoices_this_period === "number" &&
  typeof currentUser.billing_period_limit === "number" && (
    <span className="ml-1">
      {" · "}
      Usage:{" "}
      <span
        className={
          currentUser.invoices_this_period >= currentUser.billing_period_limit
            ? "text-red-600 font-medium"
            : currentUser.invoices_this_period >= currentUser.billing_period_limit * 0.9
            ? "text-amber-600 font-medium"
            : "font-medium"
        }
      >
        {currentUser.invoices_this_period} / {currentUser.billing_period_limit}
      </span>
    </span>
  )}
              </p>
            )}
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate("/billing")}
              className="text-sm text-blue-600 hover:underline font-medium"
            >
              Billing
            </button>
            <button
              onClick={() => navigate("/team")}
              className="text-sm text-blue-600 hover:underline font-medium"
            >
              Team
            </button>
            {currentUser?.role === "admin" && (
              <button
                onClick={() => navigate("/admin")}
                className="text-sm text-purple-600 hover:underline font-medium"
              >
                Admin Panel
              </button>
            )}
            <button onClick={logout} className="text-sm text-gray-600 hover:underline">
              Log out
            </button>
          </div>
        </div>

        {checkoutNotice && (
          <div
            className={`mb-4 rounded-lg border px-4 py-3 text-sm flex justify-between items-start gap-4 ${
              checkoutNotice.ok
                ? "border-green-200 bg-green-50 text-green-800"
                : "border-amber-200 bg-amber-50 text-amber-800"
            }`}
          >
            <span>{checkoutNotice.text}</span>
            <button onClick={() => setCheckoutNotice(null)} className="text-xs underline shrink-0">Dismiss</button>
          </div>
        )}

        {/* CURRENT UPLOAD */}
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
            disabled={uploading}
            busy={uploading}
            idleText="Drag and drop a PDF or image invoice here, or click to choose a file"
            onFile={handleFile}
            onReject={setMessage}
          />

          {uploading && (
            <div className="mt-4">
              <div className="flex justify-between text-xs text-gray-500 mb-1">
                <span>{currentStage.label}</span>
                <span>{currentStage.percent}%</span>
              </div>
              <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 rounded-full transition-all duration-700 ease-out"
                  style={{ width: `${currentStage.percent}%` }}
                />
              </div>
            </div>
          )}
        </div>

        {message && (
          <div className="flex items-center gap-3 mb-4">
            <p className="text-sm text-blue-700">{message}</p>
            {lastFile && !uploading && language !== "auto" && lastDetectedLanguage && lastDetectedLanguage !== language && (
              <button
                onClick={handleRetryWithDifferentLanguage}
                className="text-xs text-purple-600 hover:underline whitespace-nowrap"
                title={`Re-upload "${lastFile.name}" with the language selected above`}
              >
                🔁 Try again with selected language
              </button>
            )}
          </div>
        )}

        {/* CSV EXPORT */}
        <ExportPanel />

        {/* UPLOAD HISTORY */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <button
            onClick={() => setHistoryOpen((v) => !v)}
            className="w-full flex justify-between items-center p-4 text-left hover:bg-gray-50"
          >
            <span className="font-semibold text-gray-800">
              Upload History{" "}
              <span className="text-gray-400 font-normal text-sm">
                ({docs.length})
              </span>
            </span>
            <span className="text-gray-400 text-sm">
              {historyOpen ? "Hide ▲" : "Show ▼"}
            </span>
          </button>

          {historyOpen && (
            <table className="w-full text-left border-t">
              <thead className="bg-gray-100 text-left text-sm">
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
                      <span
                        className={`px-2 py-1 rounded text-xs font-medium ${
                          STATUS_STYLES[d.status] || ""
                        }`}
                      >
                        {d.status}
                      </span>
                    </td>
                    <td className="p-3">{new Date(d.uploaded_at).toLocaleString()}</td>
                    <td className="p-3 space-x-3">
                      {(d.status === "done" || d.status === "failed") && (
                        <button
                          onClick={() => openDocument(d.id)}
                          className="text-blue-600 hover:underline text-xs"
                        >
                          View Text
                        </button>
                      )}
                      {d.status === "done" && (
                        <button
                          onClick={() => {
                            setReviewingDocId(d.id);
                            setReviewingLanguage(d.language === "auto" ? d.detected_language ?? "en" : d.language);
                          }}
                          className="text-purple-600 hover:underline text-xs"
                        >
                          Review &amp; Save
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {docs.length === 0 && (
                  <tr>
                    <td colSpan={4} className="p-3 text-center text-gray-400">
                      No documents yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {viewingDoc && (
        <div
          className="fixed inset-0 bg-black/40 flex items-center justify-center p-4"
          onClick={() => setViewingDoc(null)}
        >
          <div
            className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] overflow-y-auto p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-start mb-4">
              <h2 className="font-bold text-lg">{viewingDoc.original_filename}</h2>
              <button onClick={() => setViewingDoc(null)} className="text-gray-400 hover:text-gray-700">
                ✕
              </button>
            </div>

            {viewingDoc.status === "failed" ? (
              <p className="text-red-600 text-sm">
                OCR failed: {viewingDoc.error_message || "Unknown error"}
              </p>
            ) : (
              <>
                <p className="text-xs text-gray-500 mb-3">
                  {viewingDoc.page_count} page(s) - language: {viewingDoc.language}
                </p>
                {viewingDoc.detected_language &&
                  viewingDoc.language !== "auto" &&
                  viewingDoc.detected_language !== viewingDoc.language && (
                    <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded px-3 py-2 mb-3">
                      ⚠ You selected "{viewingDoc.language}", but this document's text looks like
                      it's actually "{viewingDoc.detected_language}". OCR accuracy may be lower than
                      expected - consider re-uploading with the correct language selected.
                    </p>
                  )}
                <pre dir="auto" className="whitespace-pre-wrap text-sm bg-gray-50 p-4 rounded border">
                  {viewingDoc.ocr_text || "(No text was found in this document.)"}
                </pre>
              </>
            )}
          </div>
        </div>
      )}

      {reviewingDocId !== null && (
        <ReviewModal
          documentId={reviewingDocId}
          language={reviewingLanguage}
          onClose={() => setReviewingDocId(null)}
          onSaved={() => setMessage("Invoice saved successfully!")}
        />
      )}
    </div>
  );
}
