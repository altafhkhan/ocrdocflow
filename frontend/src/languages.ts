// The one list of document languages the app offers. Used by the upload
// dropdowns (dashboard + visitor page) and the CSV export panel, so adding
// a language here is enough for the UI. The backend's OCR prompt
// (ocr_providers/gemini_provider.py), language detector, CSV headers
// (services/csv_headers.py) and the review-screen labels
// (components/ReviewModal.tsx) each need a matching entry.
export interface LanguageOption {
  code: string;
  label: string;
}

export const LANGUAGES: LanguageOption[] = [
  { code: "en", label: "English" },
  { code: "ar", label: "Arabic" },
  { code: "ur", label: "Urdu" },
  { code: "fr", label: "French" },
  { code: "de", label: "German" },
  { code: "es", label: "Spanish" },
  { code: "nl", label: "Dutch" },
  { code: "zh", label: "Chinese" },
  { code: "ja", label: "Japanese" },
  { code: "ko", label: "Korean" },
];

export const AUTO_DETECT: LanguageOption = { code: "auto", label: "Auto-detect" };

// Upload dropdown: Auto-detect first, then the languages.
export const UPLOAD_LANGUAGES: LanguageOption[] = [AUTO_DETECT, ...LANGUAGES];
