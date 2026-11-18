import { useEffect, useRef, useState } from "react";
import { UPLOAD_LANGUAGES } from "../languages";
import { uploadDocument, listDocuments, getDocument, getToken, getMe, confirmCheckout, CurrentUser } from "../api";
import { useNavigate } from "react-router-dom";
import UploadDropZone from "../components/UploadDropZone";
import { FileNameCell, UploadedCell, UploadColumns } from "../components/UploadCells";
import ReviewModal from "../components/ReviewModal";
import ExportPanel from "../components/ExportPanel";

interface DocRow {
  id: number;
  original_filename: string;
  status: string;
  review_status?: string | null;
  uploaded_at: string;
  language: string;
  detected_language: string | null;
}

interface DocDetail extends DocRow {
  ocr_text: string | null;
  page_count: number | null;
  error_message: string | null;
}

const UPLOAD_STAGES = [
  { label: "Uploading file...", percent: 20 },
  { label: "Reading document (OCR)...", percent: 65 },
  { label: "Saving results...", percent: 90 },
];

export default function Dashboard() {
  const [docs, setDocs] = useState<DocRow[]>([]);
  const [language, setLanguage] = useState("auto");
  const [message, setMessage] = useState("");
  // Notes from the server about the last upload (e.g. a long invoice
  // that used more than one invoice of the plan).
  const [notices, setNotices] = useState<string[]>([]);
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
    setNotices([]);
    startStageAnimation();
    try {
      const result = await uploadDocument(file, language);
      setMessage("Done! Check Upload History below for the result.");
      setNotices(result.notices ?? []);
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
    <div className="min-h-screen bg-gray-50 p-4 sm:p-8">
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
          <p className="text-xs text-gray-500 mt-2">
            Each invoice in a file counts once towards your plan. An invoice with more than 25 line
            items counts as 1 invoice for every 25 line items (for example, 100 line items = 4 invoices).
          </p>

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

        {notices.length > 0 && (
          <div role="status" className="mb-4 rounded border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            {notices.map((n, i) => (
              <p key={i}>{n}</p>
            ))}
          </div>
        )}

        {/* CSV / EXCEL EXPORT */}
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
            <table className="w-full table-fixed text-left border-t">
              <UploadColumns />
              <thead className="bg-gray-100 text-left text-sm">
                <tr>
                  <th className="p-3">File</th>
                  <th className="py-3 px-2">Uploaded</th>
                  <th className="p-3"></th>
                </tr>
              </thead>
              <tbody>
                {docs.map((d) => (
                  <tr key={d.id} className="border-t text-sm">
                    <FileNameCell name={d.original_filename} status={d.status} reviewStatus={d.review_status} />
                    <UploadedCell at={d.uploaded_at} />
                    <td className="p-3 align-top">
                      {d.status === "failed" && (
                        <button
                          onClick={() => openDocument(d.id)}
                          className="block text-left text-blue-600 hover:underline text-xs"
                        >
                          See why
                        </button>
                      )}
                      {d.status === "done" && (
                        <button
                          onClick={() => {
                            setReviewingDocId(d.id);
                            setReviewingLanguage(d.language === "auto" ? d.detected_language ?? "en" : d.language);
                          }}
                          className="block text-left text-purple-600 hover:underline text-xs"
                        >
                          Review &amp; Save
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {docs.length === 0 && (
                  <tr>
                    <td colSpan={3} className="p-3 text-center text-gray-400">
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

            <p className="text-red-600 text-sm">
              OCR failed: {viewingDoc.error_message || "Unknown error"}
            </p>
          </div>
        </div>
      )}

      {reviewingDocId !== null && (
        <ReviewModal
          documentId={reviewingDocId}
          language={reviewingLanguage}
          onClose={() => setReviewingDocId(null)}
          onSaved={() => {
            setMessage("Invoice saved successfully!");
            refreshList(); // the row's tag changes from "done" to "saved"
          }}
        />
      )}
    </div>
  );
}
