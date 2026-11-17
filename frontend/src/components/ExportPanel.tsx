import { useEffect, useState } from "react";
import { downloadExport, getMe, saveExportFormat, ExportFormat } from "../api";
import { LANGUAGES } from "../languages";

const FORMATS: { value: ExportFormat; label: string; hint: string }[] = [
  { value: "csv", label: "CSV", hint: "Plain text, for importing into accounting or ERP software" },
  { value: "xlsx", label: "Excel (.xlsx)", hint: "A formatted workbook that opens directly in Excel" },
];

export default function ExportPanel() {
  const today = new Date().toISOString().slice(0, 10);
  const [startDate, setStartDate] = useState(today);
  const [endDate, setEndDate] = useState(today);
  const [language, setLanguage] = useState("en");
  const [documentLanguage, setDocumentLanguage] = useState("all");
  // The format is remembered on the user's account, so it is the same on
  // every device after logging in.
  const [format, setFormat] = useState<ExportFormat>("csv");
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);

  useEffect(() => {
    getMe()
      .then((me) => setFormat(me.export_format === "xlsx" ? "xlsx" : "csv"))
      .catch(() => {});
  }, []);

  function chooseFormat(next: ExportFormat) {
    setFormat(next);
    // Saved quietly; if it fails the choice still applies to this download.
    saveExportFormat(next).catch(() => {});
  }

  async function handleDownload() {
    setDownloading(true);
    setError("");
    try {
      await downloadExport(format, startDate, endDate, language, documentLanguage);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setDownloading(false);
    }
  }

  const formatLabel = format === "xlsx" ? "Excel" : "CSV";

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden mb-4">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex justify-between items-center p-4 text-left hover:bg-gray-50"
      >
        <span className="font-semibold text-gray-800">Download invoices (CSV or Excel)</span>
        <span className="text-gray-400 text-sm">{open ? "Hide ▲" : "Show ▼"}</span>
      </button>

      {open && (
        <div className="p-4 border-t">
          <p className="text-xs text-gray-500 mb-3">
            Downloads your saved (reviewed and confirmed) invoices for the selected date range,
            one row per line item, ready for your accounting/ERP software or for Excel.
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

          <div className="grid grid-cols-2 gap-3 mb-3">
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

          <fieldset className="mb-4">
            <legend className="text-sm text-gray-600 mb-1">File format</legend>
            <div className="grid grid-cols-2 gap-3">
              {FORMATS.map((f) => (
                <label
                  key={f.value}
                  className={`flex items-start gap-2 border rounded px-3 py-2 text-sm cursor-pointer ${
                    format === f.value ? "border-blue-500 bg-blue-50" : "hover:bg-gray-50"
                  }`}
                >
                  <input
                    type="radio"
                    name="export-format"
                    value={f.value}
                    checked={format === f.value}
                    onChange={() => chooseFormat(f.value)}
                    className="mt-1"
                  />
                  <span>
                    <span className="block font-medium text-gray-800">{f.label}</span>
                    <span className="block text-xs text-gray-500">{f.hint}</span>
                  </span>
                </label>
              ))}
            </div>
            <p className="text-xs text-gray-500 mt-1">Your choice is remembered for next time.</p>
          </fieldset>

          {error && <p className="text-sm text-red-600 mb-3">{error}</p>}

          <button
            onClick={handleDownload}
            disabled={downloading}
            className="px-4 py-2 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 text-sm"
          >
            {downloading ? "Preparing download..." : `Download ${formatLabel}`}
          </button>
        </div>
      )}
    </div>
  );
}
