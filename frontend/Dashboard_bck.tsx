import { useEffect, useRef, useState } from "react";
import { uploadDocument, listDocuments, getDocument, getToken } from "../api";
import { useNavigate } from "react-router-dom";

interface DocRow {
  id: number;
  original_filename: string;
  status: string;
  uploaded_at: string;
}

interface DocDetail extends DocRow {
  ocr_text: string | null;
  page_count: number | null;
  error_message: string | null;
  language: string;
}

const STATUS_STYLES: Record<string, string> = {
  uploaded: "bg-gray-100 text-gray-700",
  processing: "bg-yellow-100 text-yellow-800",
  done: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

export default function Dashboard() {
  const [docs, setDocs] = useState<DocRow[]>([]);
  const [language, setLanguage] = useState("en");
  const [message, setMessage] = useState("");
  const [uploading, setUploading] = useState(false);
  const [viewingDoc, setViewingDoc] = useState<DocDetail | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!getToken()) {
      navigate("/login");
      return;
    }
    refreshList();
  }, []);

  async function refreshList() {
    try {
      const data = await listDocuments();
      setDocs(data);
    } catch (err: any) {
      setMessage(err.message);
    }
  }

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setMessage("Uploading and reading document - this can take a little while...");
    try {
      await uploadDocument(file, language);
      setMessage("Done! Check the status column below.");
      refreshList();
    } catch (err: any) {
      setMessage(err.message);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
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

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-3xl mx-auto">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold">Your Documents</h1>
          <button onClick={logout} className="text-sm text-gray-600 hover:underline">
            Log out
          </button>
        </div>

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
            <option value="en">English</option>
            <option value="ar">Arabic</option>
          </select>

          <label
            className={`block border-2 border-dashed rounded-lg p-6 text-center ${
              uploading
                ? "border-gray-200 text-gray-400"
                : "border-gray-300 cursor-pointer hover:border-blue-400 text-gray-600"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.jpg,.jpeg,.png"
              className="hidden"
              onChange={handleFileChange}
              disabled={uploading}
            />
            {uploading ? "Working on it..." : "Click to upload a PDF or image invoice"}
          </label>
        </div>

        {message && <p className="text-sm text-blue-700 mb-4">{message}</p>}

        <table className="w-full bg-white rounded-lg shadow overflow-hidden">
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
                  <span className={`px-2 py-1 rounded text-xs font-medium ${STATUS_STYLES[d.status] || ""}`}>
                    {d.status}
                  </span>
                </td>
                <td className="p-3">{new Date(d.uploaded_at).toLocaleString()}</td>
                <td className="p-3">
                  {(d.status === "done" || d.status === "failed") && (
                    <button
                      onClick={() => openDocument(d.id)}
                      className="text-blue-600 hover:underline text-xs"
                    >
                      View Text
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
                <pre className="whitespace-pre-wrap text-sm bg-gray-50 p-4 rounded border">
                  {viewingDoc.ocr_text || "(No text was found in this document.)"}
                </pre>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
