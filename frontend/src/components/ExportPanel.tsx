import { useState } from "react";
import { downloadCsv } from "../api";
import { LANGUAGES } from "../languages";

export default function ExportPanel() {
  const today = new Date().toISOString().slice(0, 10);
  const [startDate, setStartDate] = useState(today);
  const [endDate, setEndDate] = useState(today);
  const [language, setLanguage] = useState("en");
  const [documentLanguage, setDocumentLanguage] = useState("all");
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);

  async function handleDownload() {
    setDownloading(true);
    setError("");
    try {
      await downloadCsv(startDate, endDate, language, documentLanguage);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden mb-4">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex justify-between items-center p-4 text-left hover:bg-gray-50"
      >
        <span className="font-semibold text-gray-800">Download CSV</span>
        <span className="text-gray-400 text-sm">{open ? "Hide ▲" : "Show ▼"}</span>
      </button>

      {open && (
        <div className="p-4 border-t">
          <p className="text-xs text-gray-500 mb-3">
            Exports your saved (reviewed and confirmed) invoices for the selected date range,
            formatted so you can import them into your accounting/ERP software.
          </p>

          <div className="grid grid-cols-2 gap-3 mb-3">
            <label className="block text-sm">
              <span className="block text-gray-600 mb-1">From</span>
              <input
                type="date"
                value={startDate}
                max={endDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-full border rounded px-3 py-2"
              />
            </label>
            <label className="block text-sm">
              <span className="block text-gray-600 mb-1">To</span>
              <input
                type="date"
                value={endDate}
                min={startDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="w-full border rounded px-3 py-2"
              />
            </label>
          </div>

          <div className="grid grid-cols-2 gap-3 mb-4">
            <label className="block text-sm">
              <span className="block text-gray-600 mb-1">Invoice language</span>
              <select
                value={documentLanguage}
                onChange={(e) => setDocumentLanguage(e.target.value)}
                className="w-full border rounded px-3 py-2"
              >
                <option value="all">All languages</option>
                {LANGUAGES.map((l) => (
                  <option key={l.code} value={l.code}>{l.label}</option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="block text-gray-600 mb-1">Column headings in</span>
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="w-full border rounded px-3 py-2"
              >
                {LANGUAGES.map((l) => (
                  <option key={l.code} value={l.code}>{l.label}</option>
                ))}
              </select>
            </label>
          </div>

          {error && <p className="text-sm text-red-600 mb-3">{error}</p>}

          <button
            onClick={handleDownload}
            disabled={downloading}
            className="px-4 py-2 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 text-sm"
          >
            {downloading ? "Preparing download..." : "Download CSV"}
          </button>
        </div>
      )}
    </div>
  );
}
