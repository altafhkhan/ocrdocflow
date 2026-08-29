import { useEffect, useState } from "react";
import { getExtraction, confirmExtraction, ExtractionData, ExtractionItem, ValidationWarning } from "../api";

interface Props {
  documentId: number;
  onClose: () => void;
  onSaved: () => void;
}

// Small reusable labeled input - keeps the form below readable instead of
// repeating the same 5 lines of JSX for every field.
function Field({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string | number | null;
  onChange: (v: string) => void;
}) {
  return (
    <label className="block text-sm mb-3">
      <span className="block text-gray-600 mb-1">{label}</span>
      <input
        type="text"
        dir="auto"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        className="w-full border rounded px-3 py-2"
      />
    </label>
  );
}

export default function ReviewModal({ documentId, onClose, onSaved }: Props) {
  const [data, setData] = useState<ExtractionData | null>(null);
  const [invoiceIndex, setInvoiceIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [warnings, setWarnings] = useState<ValidationWarning[]>([]);

  useEffect(() => {
    setLoading(true);
    setWarnings([]);
    setError("");
    getExtraction(documentId, invoiceIndex)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [documentId, invoiceIndex]);

  function updateField(field: keyof ExtractionData, value: string) {
    if (!data) return;
    setData({ ...data, [field]: value === "" ? null : value });
  }

  function updateItem(index: number, field: keyof ExtractionItem, value: string) {
    if (!data) return;
    const items = [...data.items];
    items[index] = { ...items[index], [field]: value === "" ? null : value };
    setData({ ...data, items });
  }

  async function handleSave() {
    if (!data) return;
    setSaving(true);
    setError("");
    try {
      // Numbers were edited as text in the inputs - convert back before
      // sending. Blank stays as null rather than becoming 0/NaN.
      const toNumber = (v: unknown) =>
        v === null || v === "" ? null : Number(v);

      const payload: ExtractionData = {
        ...data,
        sub_total: toNumber(data.sub_total),
        tax: toNumber(data.tax),
        discount: toNumber(data.discount),
        grand_total: toNumber(data.grand_total),
        items: data.items.map((item) => ({
          ...item,
          qty: toNumber(item.qty),
          unit_price: toNumber(item.unit_price),
          total_price: toNumber(item.total_price),
        })),
      };
      const result = await confirmExtraction(documentId, payload, invoiceIndex);
      onSaved();
      if (result.warnings && result.warnings.length > 0) {
        // Data IS saved already - but worth a second look before closing.
        setWarnings(result.warnings);
      } else {
        onClose();
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[85vh] overflow-y-auto p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-start mb-4">
          <div>
            <h2 className="font-bold text-lg">Review Extracted Data</h2>
            <p className="text-xs text-gray-500">
              Check the fields below and correct anything that's wrong before saving.
            </p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700">
            ✕
          </button>
        </div>

        {data && data.total_invoices > 1 && (
          <div className="flex items-center justify-center gap-3 mb-4 bg-gray-50 border rounded py-2">
            <button
              onClick={() => setInvoiceIndex((i) => Math.max(0, i - 1))}
              disabled={invoiceIndex === 0 || loading}
              className="px-2 py-1 text-sm rounded hover:bg-gray-200 disabled:opacity-30 disabled:hover:bg-transparent"
            >
              ← Back
            </button>
            <span className="text-sm text-gray-600 font-medium">
              Invoice {invoiceIndex + 1} of {data.total_invoices}
            </span>
            <button
              onClick={() => setInvoiceIndex((i) => Math.min(data.total_invoices - 1, i + 1))}
              disabled={invoiceIndex >= data.total_invoices - 1 || loading}
              className="px-2 py-1 text-sm rounded hover:bg-gray-200 disabled:opacity-30 disabled:hover:bg-transparent"
            >
              Next →
            </button>
          </div>
        )}

        {loading && <p className="text-sm text-gray-500">Loading...</p>}
        {error && <p className="text-sm text-red-600 mb-3">{error}</p>}

        {data && (
          <>
            {data.status === "saved" && (
              <p className="text-sm text-green-700 bg-green-50 border border-green-200 rounded px-3 py-2 mb-4">
                This invoice was already saved. You can still edit and save again.
              </p>
            )}

            {warnings.length > 0 && (
              <div className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded px-3 py-2 mb-4">
                <p className="font-semibold mb-1">
                  Saved - but please double-check {warnings.length === 1 ? "this" : "these"}:
                </p>
                <ul className="list-disc list-inside space-y-0.5">
                  {warnings.map((w, i) => (
                    <li key={i}>{w.message}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="grid grid-cols-2 gap-x-4">
              <Field label="Invoice Number" value={data.invoice_number} onChange={(v) => updateField("invoice_number", v)} />
              <Field label="Currency" value={data.currency} onChange={(v) => updateField("currency", v)} />
              <Field label="Invoice Date" value={data.invoice_date} onChange={(v) => updateField("invoice_date", v)} />
              <Field label="Due Date" value={data.due_date} onChange={(v) => updateField("due_date", v)} />
              <Field label="Client Name" value={data.client_name} onChange={(v) => updateField("client_name", v)} />
              <Field label="Client Company" value={data.client_company} onChange={(v) => updateField("client_company", v)} />
              <Field label="Client Email" value={data.client_email} onChange={(v) => updateField("client_email", v)} />
            </div>

            <h3 className="font-semibold text-sm text-gray-700 mt-2 mb-2">Line Items</h3>
            <table className="w-full text-sm mb-4">
              <thead className="text-left text-gray-500">
                <tr>
                  <th className="pb-1">Description</th>
                  <th className="pb-1 w-20">Qty</th>
                  <th className="pb-1 w-28">Unit Price</th>
                  <th className="pb-1 w-28">Total Price</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item, i) => (
                  <tr key={item.id ?? i} className="border-t">
                    <td className="py-1 pr-2">
                      <input
                        type="text"
                        dir="auto"
                        value={item.description ?? ""}
                        onChange={(e) => updateItem(i, "description", e.target.value)}
                        className="w-full border rounded px-2 py-1"
                      />
                    </td>
                    <td className="py-1 pr-2">
                      <input
                        type="text"
                        value={item.qty ?? ""}
                        onChange={(e) => updateItem(i, "qty", e.target.value)}
                        className="w-full border rounded px-2 py-1"
                        placeholder="?"
                      />
                    </td>
                    <td className="py-1 pr-2">
                      <input
                        type="text"
                        value={item.unit_price ?? ""}
                        onChange={(e) => updateItem(i, "unit_price", e.target.value)}
                        className="w-full border rounded px-2 py-1"
                      />
                    </td>
                    <td className="py-1">
                      <input
                        type="text"
                        value={item.total_price ?? ""}
                        onChange={(e) => updateItem(i, "total_price", e.target.value)}
                        className="w-full border rounded px-2 py-1"
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div className="grid grid-cols-2 gap-x-4">
              <Field label="Sub-Total" value={data.sub_total} onChange={(v) => updateField("sub_total", v)} />
              <Field label="Tax" value={data.tax} onChange={(v) => updateField("tax", v)} />
              <Field label="Discount" value={data.discount} onChange={(v) => updateField("discount", v)} />
              <Field label="Grand Total" value={data.grand_total} onChange={(v) => updateField("grand_total", v)} />
            </div>

            <div className="flex justify-end gap-2 mt-4">
              <button
                onClick={onClose}
                className="px-4 py-2 rounded border text-gray-600 hover:bg-gray-50"
                disabled={saving}
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                className="px-4 py-2 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
                disabled={saving}
              >
                {saving ? "Saving..." : "Save"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}