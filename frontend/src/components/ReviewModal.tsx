import { useEffect, useState } from "react";
import { getExtraction, confirmExtraction, ExtractionData, ExtractionItem, ValidationWarning } from "../api";

interface Props {
  documentId: number;
  language: string;
  onClose: () => void;
  onSaved: () => void;
}

// UI text for the review screen, in English and Arabic. The document's
// own DATA (client names, addresses, etc) was never translated - only
// these fixed interface labels are. Add more languages here as needed.
const TRANSLATIONS = {
  en: {
    title: "Review Extracted Data",
    subtitle: "Check the fields below and correct anything that's wrong before saving.",
    invoiceOf: (i: number, n: number) => `Invoice ${i} of ${n}`,
    back: "\u2190 Back",
    next: "Next \u2192",
    alreadySaved: "This invoice was already saved. You can still edit and save again.",
    warningsTitle: (n: number) => `Saved - but please double-check ${n === 1 ? "this" : "these"}:`,
    invoiceNumber: "Invoice Number",
    currency: "Currency",
    invoiceDate: "Invoice Date",
    dueDate: "Due Date",
    clientName: "Client Name",
    clientCompany: "Client Company",
    clientEmail: "Client Email",
    lineItems: "Line Items",
    description: "Description",
    qty: "Qty",
    unitPrice: "Unit Price",
    totalPrice: "Total Price",
    subTotal: "Sub-Total",
    tax: "Tax",
    discount: "Discount",
    grandTotal: "Grand Total",
    cancel: "Cancel",
    save: "Save",
    saving: "Saving...",
    loading: "Loading...",
  },
  ar: {
    title: "مراجعة البيانات المستخرجة",
    subtitle: "تحقق من الحقول أدناه وصحح أي خطأ قبل الحفظ.",
    invoiceOf: (i: number, n: number) => `فاتورة ${i} من ${n}`,
    back: "\u2192 السابق",
    next: "التالي \u2190",
    alreadySaved: "تم حفظ هذه الفاتورة مسبقاً. يمكنك تعديلها وحفظها مرة أخرى.",
    warningsTitle: (n: number) => `تم الحفظ - يرجى مراجعة ${n === 1 ? "هذا" : "هذه"}:`,
    invoiceNumber: "رقم الفاتورة",
    currency: "العملة",
    invoiceDate: "تاريخ الفاتورة",
    dueDate: "تاريخ الاستحقاق",
    clientName: "اسم العميل",
    clientCompany: "اسم الشركة",
    clientEmail: "البريد الإلكتروني",
    lineItems: "بنود الفاتورة",
    description: "الوصف",
    qty: "الكمية",
    unitPrice: "سعر الوحدة",
    totalPrice: "السعر الإجمالي",
    subTotal: "المجموع الفرعي",
    tax: "الضريبة",
    discount: "الخصم",
    grandTotal: "الإجمالي الكلي",
    cancel: "إلغاء",
    save: "حفظ",
    saving: "جارٍ الحفظ...",
    loading: "جارٍ التحميل...",
  },
  ur: {
    title: "نکالا گیا ڈیٹا چیک کریں",
    subtitle: "نیچے دیے گئے خانے چیک کریں اور محفوظ کرنے سے پہلے غلطیاں درست کریں۔",
    invoiceOf: (i: number, n: number) => `انوائس ${i} از ${n}`,
    back: "→ پچھلا",
    next: "اگلا ←",
    alreadySaved: "یہ انوائس پہلے ہی محفوظ ہو چکی ہے۔ آپ اسے دوبارہ ترمیم کر کے محفوظ کر سکتے ہیں۔",
    warningsTitle: (n: number) => `محفوظ ہو گیا - براہ کرم ${n === 1 ? "یہ" : "یہ سب"} دوبارہ چیک کریں:`,
    invoiceNumber: "انوائس نمبر",
    currency: "کرنسی",
    invoiceDate: "انوائس کی تاریخ",
    dueDate: "ادائیگی کی آخری تاریخ",
    clientName: "گاہک کا نام",
    clientCompany: "گاہک کی کمپنی",
    clientEmail: "گاہک کا ای میل",
    lineItems: "اشیاء کی تفصیل",
    description: "تفصیل",
    qty: "مقدار",
    unitPrice: "فی یونٹ قیمت",
    totalPrice: "کل قیمت",
    subTotal: "ذیلی میزان",
    tax: "ٹیکس",
    discount: "رعایت",
    grandTotal: "کل میزان",
    cancel: "منسوخ",
    save: "محفوظ کریں",
    saving: "محفوظ ہو رہا ہے...",
    loading: "لوڈ ہو رہا ہے...",
  },
};

// Small reusable labeled input - keeps the form below readable instead of
// repeating the same 5 lines of JSX for every field.
function Field({
  label,
  value,
  onChange,
  dir,
}: {
  label: string;
  value: string | number | null;
  onChange: (v: string) => void;
  dir: "rtl" | "ltr";
}) {
  return (
    <label className="block text-sm mb-3">
      <span className="block text-gray-600 mb-1">{label}</span>
      <input
        type="text"
        dir={dir}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        className="w-full border rounded px-3 py-2"
      />
    </label>
  );
}

export default function ReviewModal({ documentId, language, onClose, onSaved }: Props) {
  const [data, setData] = useState<ExtractionData | null>(null);
  const [invoiceIndex, setInvoiceIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [warnings, setWarnings] = useState<ValidationWarning[]>([]);

  // Arabic and Urdu are both right-to-left and have their own labels.
  const isRTL = language === "ar" || language === "ur";
  const t = TRANSLATIONS[language === "ar" ? "ar" : language === "ur" ? "ur" : "en"];

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
        dir={isRTL ? "rtl" : "ltr"}
        className="bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[85vh] overflow-y-auto p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-start mb-4">
          <div>
            <h2 className="font-bold text-lg">{t.title}</h2>
            <p className="text-xs text-gray-500">{t.subtitle}</p>
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
              {t.back}
            </button>
            <span className="text-sm text-gray-600 font-medium">
              {t.invoiceOf(invoiceIndex + 1, data.total_invoices)}
            </span>
            <button
              onClick={() => setInvoiceIndex((i) => Math.min(data.total_invoices - 1, i + 1))}
              disabled={invoiceIndex >= data.total_invoices - 1 || loading}
              className="px-2 py-1 text-sm rounded hover:bg-gray-200 disabled:opacity-30 disabled:hover:bg-transparent"
            >
              {t.next}
            </button>
          </div>
        )}

        {loading && <p className="text-sm text-gray-500">{t.loading}</p>}
        {error && <p className="text-sm text-red-600 mb-3">{error}</p>}

        {data && (
          <>
            {data.status === "saved" && (
              <p className="text-sm text-green-700 bg-green-50 border border-green-200 rounded px-3 py-2 mb-4">
                {t.alreadySaved}
              </p>
            )}

            {warnings.length > 0 && (
              <div className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded px-3 py-2 mb-4">
                <p className="font-semibold mb-1">{t.warningsTitle(warnings.length)}</p>
                <ul className="list-disc list-inside space-y-0.5">
                  {warnings.map((w, i) => (
                    <li key={i}>{w.message}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="grid grid-cols-2 gap-x-4">
              <Field label={t.invoiceNumber} value={data.invoice_number} onChange={(v) => updateField("invoice_number", v)} dir={isRTL ? "rtl" : "ltr"} />
              <Field label={t.currency} value={data.currency} onChange={(v) => updateField("currency", v)} dir={isRTL ? "rtl" : "ltr"} />
              <Field label={t.invoiceDate} value={data.invoice_date} onChange={(v) => updateField("invoice_date", v)} dir={isRTL ? "rtl" : "ltr"} />
              <Field label={t.dueDate} value={data.due_date} onChange={(v) => updateField("due_date", v)} dir={isRTL ? "rtl" : "ltr"} />
              <Field label={t.clientName} value={data.client_name} onChange={(v) => updateField("client_name", v)} dir={isRTL ? "rtl" : "ltr"} />
              <Field label={t.clientCompany} value={data.client_company} onChange={(v) => updateField("client_company", v)} dir={isRTL ? "rtl" : "ltr"} />
              <Field label={t.clientEmail} value={data.client_email} onChange={(v) => updateField("client_email", v)} dir={isRTL ? "rtl" : "ltr"} />
            </div>

            <h3 className="font-semibold text-sm text-gray-700 mt-2 mb-2">{t.lineItems}</h3>
            <table className="w-full text-sm mb-4">
              <thead className="text-gray-500" style={{ textAlign: isRTL ? "right" : "left" }}>
                <tr>
                  <th className="pb-1">{t.description}</th>
                  <th className="pb-1 w-20">{t.qty}</th>
                  <th className="pb-1 w-28">{t.unitPrice}</th>
                  <th className="pb-1 w-28">{t.totalPrice}</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item, i) => (
                  <tr key={item.id ?? i} className="border-t">
                    <td className="py-1 px-1">
                      <input
                        type="text"
                        dir={isRTL ? "rtl" : "ltr"}
                        value={item.description ?? ""}
                        onChange={(e) => updateItem(i, "description", e.target.value)}
                        className="w-full border rounded px-2 py-1"
                      />
                    </td>
                    <td className="py-1 px-1">
                      <input
                        type="text"
                        value={item.qty ?? ""}
                        onChange={(e) => updateItem(i, "qty", e.target.value)}
                        className="w-full border rounded px-2 py-1"
                        placeholder="?"
                      />
                    </td>
                    <td className="py-1 px-1">
                      <input
                        type="text"
                        value={item.unit_price ?? ""}
                        onChange={(e) => updateItem(i, "unit_price", e.target.value)}
                        className="w-full border rounded px-2 py-1"
                      />
                    </td>
                    <td className="py-1 px-1">
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
              <Field label={t.subTotal} value={data.sub_total} onChange={(v) => updateField("sub_total", v)} dir={isRTL ? "rtl" : "ltr"} />
              <Field label={t.tax} value={data.tax} onChange={(v) => updateField("tax", v)} dir={isRTL ? "rtl" : "ltr"} />
              <Field label={t.discount} value={data.discount} onChange={(v) => updateField("discount", v)} dir={isRTL ? "rtl" : "ltr"} />
              <Field label={t.grandTotal} value={data.grand_total} onChange={(v) => updateField("grand_total", v)} dir={isRTL ? "rtl" : "ltr"} />
            </div>

            <div className="flex justify-end gap-2 mt-4">
              <button
                onClick={onClose}
                className="px-4 py-2 rounded border text-gray-600 hover:bg-gray-50"
                disabled={saving}
              >
                {t.cancel}
              </button>
              <button
                onClick={handleSave}
                className="px-4 py-2 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
                disabled={saving}
              >
                {saving ? t.saving : t.save}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
