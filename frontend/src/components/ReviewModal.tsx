import { useEffect, useState } from "react";
import {
  getExtraction,
  confirmExtraction,
  getDocumentFile,
  ExtractionData,
  ExtractionItem,
  ValidationWarning,
} from "../api";

interface Props {
  documentId: number;
  language: string;
  onClose: () => void;
  onSaved: () => void;
}

interface Labels {
  title: string;
  subtitle: string;
  invoiceOf: (i: number, n: number) => string;
  back: string;
  next: string;
  alreadySaved: string;
  warningsTitle: (n: number) => string;
  invoiceNumber: string;
  currency: string;
  invoiceDate: string;
  dueDate: string;
  clientName: string;
  clientCompany: string;
  clientEmail: string;
  lineItems: string;
  description: string;
  qty: string;
  unitPrice: string;
  totalPrice: string;
  subTotal: string;
  tax: string;
  discount: string;
  grandTotal: string;
  cancel: string;
  save: string;
  saving: string;
  loading: string;
  original: string;
  showOriginal: string;
  hideOriginal: string;
  previewUnavailable: string;
}

// UI text for the review screen, per language. The document's own DATA
// (client names, addresses, etc) is never translated - only these fixed
// interface labels are. Languages without an entry fall back to English.
const TRANSLATIONS: Record<string, Labels> = {
  en: {
    title: "Review Extracted Data",
    subtitle: "Check the fields below against the original and correct anything that's wrong before saving.",
    invoiceOf: (i, n) => `Invoice ${i} of ${n}`,
    back: "← Back",
    next: "Next →",
    alreadySaved: "This invoice was already saved. You can still edit and save again.",
    warningsTitle: (n) => `Saved - but please double-check ${n === 1 ? "this" : "these"}:`,
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
    original: "Original document",
    showOriginal: "Show original",
    hideOriginal: "Hide original",
    previewUnavailable: "Preview not available.",
  },
  ar: {
    title: "مراجعة البيانات المستخرجة",
    subtitle: "قارن الحقول أدناه بالمستند الأصلي وصحح أي خطأ قبل الحفظ.",
    invoiceOf: (i, n) => `فاتورة ${i} من ${n}`,
    back: "→ السابق",
    next: "التالي ←",
    alreadySaved: "تم حفظ هذه الفاتورة مسبقاً. يمكنك تعديلها وحفظها مرة أخرى.",
    warningsTitle: (n) => `تم الحفظ - يرجى مراجعة ${n === 1 ? "هذا" : "هذه"}:`,
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
    original: "المستند الأصلي",
    showOriginal: "عرض الأصل",
    hideOriginal: "إخفاء الأصل",
    previewUnavailable: "المعاينة غير متاحة.",
  },
  ur: {
    title: "نکالا گیا ڈیٹا چیک کریں",
    subtitle: "نیچے دیے گئے خانوں کا اصل دستاویز سے موازنہ کریں اور محفوظ کرنے سے پہلے غلطیاں درست کریں۔",
    invoiceOf: (i, n) => `انوائس ${i} از ${n}`,
    back: "→ پچھلا",
    next: "اگلا ←",
    alreadySaved: "یہ انوائس پہلے ہی محفوظ ہو چکی ہے۔ آپ اسے دوبارہ ترمیم کر کے محفوظ کر سکتے ہیں۔",
    warningsTitle: (n) => `محفوظ ہو گیا - براہ کرم ${n === 1 ? "یہ" : "یہ سب"} دوبارہ چیک کریں:`,
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
    original: "اصل دستاویز",
    showOriginal: "اصل دکھائیں",
    hideOriginal: "اصل چھپائیں",
    previewUnavailable: "پیش نظارہ دستیاب نہیں۔",
  },
  fr: {
    title: "Vérifier les données extraites",
    subtitle: "Comparez les champs ci-dessous à l'original et corrigez les erreurs avant d'enregistrer.",
    invoiceOf: (i, n) => `Facture ${i} sur ${n}`,
    back: "← Précédent",
    next: "Suivant →",
    alreadySaved: "Cette facture a déjà été enregistrée. Vous pouvez encore la modifier et l'enregistrer à nouveau.",
    warningsTitle: (n) => `Enregistré - mais veuillez vérifier ${n === 1 ? "ce point" : "ces points"} :`,
    invoiceNumber: "Numéro de facture",
    currency: "Devise",
    invoiceDate: "Date de facture",
    dueDate: "Date d'échéance",
    clientName: "Nom du client",
    clientCompany: "Société du client",
    clientEmail: "E-mail du client",
    lineItems: "Lignes de facture",
    description: "Description",
    qty: "Qté",
    unitPrice: "Prix unitaire",
    totalPrice: "Prix total",
    subTotal: "Sous-total",
    tax: "TVA / Taxe",
    discount: "Remise",
    grandTotal: "Total général",
    cancel: "Annuler",
    save: "Enregistrer",
    saving: "Enregistrement...",
    loading: "Chargement...",
    original: "Document original",
    showOriginal: "Afficher l'original",
    hideOriginal: "Masquer l'original",
    previewUnavailable: "Aperçu indisponible.",
  },
  de: {
    title: "Extrahierte Daten prüfen",
    subtitle: "Vergleichen Sie die Felder unten mit dem Original und korrigieren Sie Fehler vor dem Speichern.",
    invoiceOf: (i, n) => `Rechnung ${i} von ${n}`,
    back: "← Zurück",
    next: "Weiter →",
    alreadySaved: "Diese Rechnung wurde bereits gespeichert. Sie können sie weiterhin bearbeiten und erneut speichern.",
    warningsTitle: (n) => `Gespeichert - bitte ${n === 1 ? "diesen Punkt" : "diese Punkte"} noch einmal prüfen:`,
    invoiceNumber: "Rechnungsnummer",
    currency: "Währung",
    invoiceDate: "Rechnungsdatum",
    dueDate: "Fälligkeitsdatum",
    clientName: "Kundenname",
    clientCompany: "Kundenfirma",
    clientEmail: "Kunden-E-Mail",
    lineItems: "Rechnungspositionen",
    description: "Beschreibung",
    qty: "Menge",
    unitPrice: "Einzelpreis",
    totalPrice: "Gesamtpreis",
    subTotal: "Zwischensumme",
    tax: "Steuer / MwSt.",
    discount: "Rabatt",
    grandTotal: "Gesamtbetrag",
    cancel: "Abbrechen",
    save: "Speichern",
    saving: "Wird gespeichert...",
    loading: "Wird geladen...",
    original: "Originaldokument",
    showOriginal: "Original anzeigen",
    hideOriginal: "Original ausblenden",
    previewUnavailable: "Vorschau nicht verfügbar.",
  },
  es: {
    title: "Revisar los datos extraídos",
    subtitle: "Compare los campos siguientes con el original y corrija cualquier error antes de guardar.",
    invoiceOf: (i, n) => `Factura ${i} de ${n}`,
    back: "← Anterior",
    next: "Siguiente →",
    alreadySaved: "Esta factura ya se guardó. Aún puede editarla y guardarla de nuevo.",
    warningsTitle: (n) => `Guardado - pero revise ${n === 1 ? "este punto" : "estos puntos"}:`,
    invoiceNumber: "Número de factura",
    currency: "Moneda",
    invoiceDate: "Fecha de factura",
    dueDate: "Fecha de vencimiento",
    clientName: "Nombre del cliente",
    clientCompany: "Empresa del cliente",
    clientEmail: "Correo del cliente",
    lineItems: "Líneas de la factura",
    description: "Descripción",
    qty: "Cant.",
    unitPrice: "Precio unitario",
    totalPrice: "Precio total",
    subTotal: "Subtotal",
    tax: "Impuesto / IVA",
    discount: "Descuento",
    grandTotal: "Total",
    cancel: "Cancelar",
    save: "Guardar",
    saving: "Guardando...",
    loading: "Cargando...",
    original: "Documento original",
    showOriginal: "Mostrar original",
    hideOriginal: "Ocultar original",
    previewUnavailable: "Vista previa no disponible.",
  },
  nl: {
    title: "Geëxtraheerde gegevens controleren",
    subtitle: "Vergelijk de velden hieronder met het origineel en corrigeer fouten voordat u opslaat.",
    invoiceOf: (i, n) => `Factuur ${i} van ${n}`,
    back: "← Vorige",
    next: "Volgende →",
    alreadySaved: "Deze factuur is al opgeslagen. U kunt deze nog bewerken en opnieuw opslaan.",
    warningsTitle: (n) => `Opgeslagen - controleer ${n === 1 ? "dit punt" : "deze punten"} nog even:`,
    invoiceNumber: "Factuurnummer",
    currency: "Valuta",
    invoiceDate: "Factuurdatum",
    dueDate: "Vervaldatum",
    clientName: "Naam klant",
    clientCompany: "Bedrijf klant",
    clientEmail: "E-mail klant",
    lineItems: "Factuurregels",
    description: "Omschrijving",
    qty: "Aantal",
    unitPrice: "Stukprijs",
    totalPrice: "Totaalprijs",
    subTotal: "Subtotaal",
    tax: "Btw / Belasting",
    discount: "Korting",
    grandTotal: "Totaalbedrag",
    cancel: "Annuleren",
    save: "Opslaan",
    saving: "Opslaan...",
    loading: "Laden...",
    original: "Origineel document",
    showOriginal: "Origineel tonen",
    hideOriginal: "Origineel verbergen",
    previewUnavailable: "Voorbeeld niet beschikbaar.",
  },
  zh: {
    title: "核对提取的数据",
    subtitle: "请将下列字段与原件对照，保存前更正任何错误。",
    invoiceOf: (i, n) => `第 ${i} 张发票，共 ${n} 张`,
    back: "← 上一张",
    next: "下一张 →",
    alreadySaved: "此发票已保存。您仍可编辑并再次保存。",
    warningsTitle: (n) => `已保存 - 请再次核对以下${n === 1 ? "一项" : "各项"}：`,
    invoiceNumber: "发票号码",
    currency: "币种",
    invoiceDate: "开票日期",
    dueDate: "到期日",
    clientName: "客户姓名",
    clientCompany: "客户公司",
    clientEmail: "客户邮箱",
    lineItems: "明细项目",
    description: "描述",
    qty: "数量",
    unitPrice: "单价",
    totalPrice: "金额",
    subTotal: "小计",
    tax: "税额",
    discount: "折扣",
    grandTotal: "合计",
    cancel: "取消",
    save: "保存",
    saving: "保存中...",
    loading: "加载中...",
    original: "原始文件",
    showOriginal: "显示原件",
    hideOriginal: "隐藏原件",
    previewUnavailable: "无法预览。",
  },
  ja: {
    title: "抽出データの確認",
    subtitle: "下の項目を原本と照らし合わせ、保存前に誤りを修正してください。",
    invoiceOf: (i, n) => `請求書 ${i} / ${n}`,
    back: "← 前へ",
    next: "次へ →",
    alreadySaved: "この請求書はすでに保存されています。編集して再保存できます。",
    warningsTitle: () => "保存しました - 次の点をご確認ください：",
    invoiceNumber: "請求書番号",
    currency: "通貨",
    invoiceDate: "請求日",
    dueDate: "支払期限",
    clientName: "顧客名",
    clientCompany: "顧客の会社名",
    clientEmail: "顧客のメール",
    lineItems: "明細",
    description: "品名",
    qty: "数量",
    unitPrice: "単価",
    totalPrice: "金額",
    subTotal: "小計",
    tax: "税額",
    discount: "値引き",
    grandTotal: "合計",
    cancel: "キャンセル",
    save: "保存",
    saving: "保存中...",
    loading: "読み込み中...",
    original: "原本",
    showOriginal: "原本を表示",
    hideOriginal: "原本を隠す",
    previewUnavailable: "プレビューを表示できません。",
  },
  ko: {
    title: "추출된 데이터 확인",
    subtitle: "아래 항목을 원본과 비교하고 저장하기 전에 오류를 수정하세요.",
    invoiceOf: (i, n) => `청구서 ${i} / ${n}`,
    back: "← 이전",
    next: "다음 →",
    alreadySaved: "이 청구서는 이미 저장되었습니다. 수정 후 다시 저장할 수 있습니다.",
    warningsTitle: (n) => `저장됨 - 다음 ${n === 1 ? "항목" : "항목들"}을 다시 확인하세요:`,
    invoiceNumber: "청구서 번호",
    currency: "통화",
    invoiceDate: "청구일",
    dueDate: "지급 기한",
    clientName: "고객명",
    clientCompany: "고객 회사",
    clientEmail: "고객 이메일",
    lineItems: "품목",
    description: "내역",
    qty: "수량",
    unitPrice: "단가",
    totalPrice: "금액",
    subTotal: "소계",
    tax: "세금",
    discount: "할인",
    grandTotal: "합계",
    cancel: "취소",
    save: "저장",
    saving: "저장 중...",
    loading: "불러오는 중...",
    original: "원본 문서",
    showOriginal: "원본 보기",
    hideOriginal: "원본 숨기기",
    previewUnavailable: "미리보기를 사용할 수 없습니다.",
  },
};

const RTL_LANGUAGES = ["ar", "ur"];

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

  // Side-by-side preview of the uploaded file, so the user can compare the
  // extracted values with what is actually printed/written on the page.
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewType, setPreviewType] = useState<string>("");
  const [previewError, setPreviewError] = useState(false);
  const [showPreview, setShowPreview] = useState(true);

  const isRTL = RTL_LANGUAGES.includes(language);
  const t = TRANSLATIONS[language] ?? TRANSLATIONS.en;
  const dir: "rtl" | "ltr" = isRTL ? "rtl" : "ltr";

  useEffect(() => {
    setLoading(true);
    setWarnings([]);
    setError("");
    getExtraction(documentId, invoiceIndex)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [documentId, invoiceIndex]);

  useEffect(() => {
    let url: string | null = null;
    setPreviewError(false);
    getDocumentFile(documentId)
      .then((blob) => {
        url = URL.createObjectURL(blob);
        setPreviewType(blob.type);
        setPreviewUrl(url);
      })
      .catch(() => setPreviewError(true));
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [documentId]);

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

  const preview = (
    <div className="h-full flex flex-col bg-gray-100 rounded-lg border overflow-hidden">
      <div className="px-3 py-2 text-xs font-semibold text-gray-600 border-b bg-gray-50">
        {t.original}
      </div>
      <div className="flex-1 min-h-0 overflow-auto flex items-start justify-center">
        {previewError && <p className="text-sm text-gray-500 p-4">{t.previewUnavailable}</p>}
        {!previewError && !previewUrl && <p className="text-sm text-gray-500 p-4">{t.loading}</p>}
        {previewUrl && previewType === "application/pdf" && (
          <iframe title={t.original} src={previewUrl} className="w-full h-full" />
        )}
        {previewUrl && previewType !== "application/pdf" && (
          <img src={previewUrl} alt={t.original} className="max-w-full h-auto" />
        )}
      </div>
    </div>
  );

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50"
      onClick={onClose}
    >
      <div
        dir={dir}
        className={`bg-white rounded-lg shadow-xl w-full h-[90vh] flex flex-col p-6 ${
          showPreview ? "max-w-6xl" : "max-w-3xl"
        }`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-start mb-4">
          <div>
            <h2 className="font-bold text-lg">{t.title}</h2>
            <p className="text-xs text-gray-500">{t.subtitle}</p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowPreview((v) => !v)}
              className="text-xs text-blue-600 hover:underline whitespace-nowrap"
            >
              {showPreview ? t.hideOriginal : t.showOriginal}
            </button>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-700">
              ✕
            </button>
          </div>
        </div>

        <div className={`flex-1 min-h-0 ${showPreview ? "grid grid-cols-1 md:grid-cols-2 gap-4" : ""}`}>
          {showPreview && <div className="min-h-[40vh] md:min-h-0 h-full">{preview}</div>}

          <div className="h-full overflow-y-auto pr-1">
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
                  <Field label={t.invoiceNumber} value={data.invoice_number} onChange={(v) => updateField("invoice_number", v)} dir={dir} />
                  <Field label={t.currency} value={data.currency} onChange={(v) => updateField("currency", v)} dir={dir} />
                  <Field label={t.invoiceDate} value={data.invoice_date} onChange={(v) => updateField("invoice_date", v)} dir={dir} />
                  <Field label={t.dueDate} value={data.due_date} onChange={(v) => updateField("due_date", v)} dir={dir} />
                  <Field label={t.clientName} value={data.client_name} onChange={(v) => updateField("client_name", v)} dir={dir} />
                  <Field label={t.clientCompany} value={data.client_company} onChange={(v) => updateField("client_company", v)} dir={dir} />
                  <Field label={t.clientEmail} value={data.client_email} onChange={(v) => updateField("client_email", v)} dir={dir} />
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
                            dir={dir}
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
                  <Field label={t.subTotal} value={data.sub_total} onChange={(v) => updateField("sub_total", v)} dir={dir} />
                  <Field label={t.tax} value={data.tax} onChange={(v) => updateField("tax", v)} dir={dir} />
                  <Field label={t.discount} value={data.discount} onChange={(v) => updateField("discount", v)} dir={dir} />
                  <Field label={t.grandTotal} value={data.grand_total} onChange={(v) => updateField("grand_total", v)} dir={dir} />
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
      </div>
    </div>
  );
}
