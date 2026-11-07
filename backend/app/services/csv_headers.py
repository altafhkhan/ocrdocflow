"""
CSV column headers for the invoice export, per UI language.

Column ORDER is fixed (it matches the row layout in exports.py and
visitor.py); only the words change. Keep every list exactly 15 entries.
"""

SUPPORTED_LANGUAGES = ["en", "ar", "ur", "fr", "de", "es", "nl", "zh", "ja", "ko"]

CSV_HEADERS: dict[str, list[str]] = {
    "en": [
        "Invoice Number", "Invoice Date", "Due Date", "Currency",
        "Client Name", "Client Company", "Client Email",
        "Item Description", "Qty", "Unit Price", "Total Price",
        "Sub-Total", "Tax", "Discount", "Grand Total",
    ],
    "ar": [
        "رقم الفاتورة", "تاريخ الفاتورة", "تاريخ الاستحقاق", "العملة",
        "اسم العميل", "اسم الشركة", "البريد الإلكتروني",
        "الوصف", "الكمية", "سعر الوحدة", "السعر الإجمالي",
        "المجموع الفرعي", "الضريبة", "الخصم", "الإجمالي الكلي",
    ],
    "ur": [
        "انوائس نمبر", "انوائس کی تاریخ", "ادائیگی کی آخری تاریخ", "کرنسی",
        "گاہک کا نام", "گاہک کی کمپنی", "گاہک کا ای میل",
        "تفصیل", "مقدار", "فی یونٹ قیمت", "کل قیمت",
        "ذیلی میزان", "ٹیکس", "رعایت", "کل میزان",
    ],
    "fr": [
        "Numéro de facture", "Date de facture", "Date d'échéance", "Devise",
        "Nom du client", "Société du client", "E-mail du client",
        "Désignation", "Qté", "Prix unitaire", "Prix total",
        "Sous-total", "Taxe", "Remise", "Total général",
    ],
    "de": [
        "Rechnungsnummer", "Rechnungsdatum", "Fälligkeitsdatum", "Währung",
        "Kundenname", "Kundenfirma", "Kunden-E-Mail",
        "Beschreibung", "Menge", "Einzelpreis", "Gesamtpreis",
        "Zwischensumme", "Steuer", "Rabatt", "Gesamtbetrag",
    ],
    "es": [
        "Número de factura", "Fecha de factura", "Fecha de vencimiento", "Moneda",
        "Nombre del cliente", "Empresa del cliente", "Correo del cliente",
        "Descripción", "Cant.", "Precio unitario", "Precio total",
        "Subtotal", "Impuesto", "Descuento", "Total",
    ],
    "nl": [
        "Factuurnummer", "Factuurdatum", "Vervaldatum", "Valuta",
        "Naam klant", "Bedrijf klant", "E-mail klant",
        "Omschrijving", "Aantal", "Stukprijs", "Totaalprijs",
        "Subtotaal", "Belasting", "Korting", "Totaalbedrag",
    ],
    "zh": [
        "发票号码", "开票日期", "到期日", "币种",
        "客户姓名", "客户公司", "客户邮箱",
        "描述", "数量", "单价", "金额",
        "小计", "税额", "折扣", "合计",
    ],
    "ja": [
        "請求書番号", "請求日", "支払期限", "通貨",
        "顧客名", "顧客の会社名", "顧客のメール",
        "品名", "数量", "単価", "金額",
        "小計", "税額", "値引き", "合計",
    ],
    "ko": [
        "청구서 번호", "청구일", "지급 기한", "통화",
        "고객명", "고객 회사", "고객 이메일",
        "내역", "수량", "단가", "금액",
        "소계", "세금", "할인", "합계",
    ],
}

assert all(len(v) == 15 for v in CSV_HEADERS.values())
