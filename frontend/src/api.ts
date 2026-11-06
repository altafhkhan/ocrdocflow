// In production, nginx serves the frontend and proxies /api/* to the
// backend on the same origin, so no base URL (and no CORS) is needed there.
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export function getToken() {
  return localStorage.getItem("token");
}

export async function login(email: string, password: string) {
  const body = new URLSearchParams();
  body.append("username", email);
  body.append("password", password);
  const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!res.ok) throw new Error("Login failed. Check your email and password.");
  const data = await res.json();
  localStorage.setItem("token", data.access_token);
  return data;
}

export async function register(email: string, password: string, fullName: string) {
  const res = await fetch(`${API_BASE}/api/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, full_name: fullName }),
  });
  if (!res.ok) throw new Error("Could not create account. Try a different email.");
  return res.json();
}

export interface CurrentUser {
  id: number;
  email: string;
  full_name: string | null;
  role: string;
  plan: string;
  invoices_this_period: number | null;
  billing_period_limit: number | null;
  billing_period_start: string | null;
}

export async function getMe(): Promise<CurrentUser> {
  const res = await fetch(`${API_BASE}/api/v1/auth/me`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!res.ok) throw new Error("Could not load current user.");
  return res.json();
}

export async function uploadDocument(file: File, language: string) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("language", language);
  const res = await fetch(`${API_BASE}/api/v1/documents/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${getToken()}` },
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Upload failed." }));
    throw new Error(err.detail);
  }
  return res.json();
}

export async function listDocuments() {
  const res = await fetch(`${API_BASE}/api/v1/documents/`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!res.ok) throw new Error("Could not load documents.");
  return res.json();
}

export async function getDocument(id: number) {
  const res = await fetch(`${API_BASE}/api/v1/documents/${id}`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!res.ok) throw new Error("Could not load document.");
  return res.json();
}

// --- Phase 3/4: field extraction, review, and confirm --------------------

export interface ExtractionItem {
  id?: number;
  description: string | null;
  qty: number | null;
  unit_price: number | null;
  total_price: number | null;
}

export interface ExtractionData {
  invoice_index: number;
  total_invoices: number;
  status: string;
  invoice_number: string | null;
  invoice_date: string | null;
  due_date: string | null;
  currency: string | null;
  client_name: string | null;
  client_company: string | null;
  client_email: string | null;
  sub_total: number | null;
  tax: number | null;
  discount: number | null;
  grand_total: number | null;
  items: ExtractionItem[];
}

export async function getExtraction(documentId: number, invoiceIndex: number = 0): Promise<ExtractionData> {
  const res = await fetch(`${API_BASE}/api/v1/documents/${documentId}/extraction?invoice_index=${invoiceIndex}`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Could not load extracted data." }));
    throw new Error(err.detail);
  }
  return res.json();
}

export interface ValidationWarning {
  level: string;
  field: string;
  message: string;
}

export interface ConfirmResponse {
  invoice_id: number;
  invoice_index: number;
  total_invoices: number;
  status: string;
  warnings: ValidationWarning[];
}

export async function confirmExtraction(documentId: number, data: ExtractionData, invoiceIndex: number = 0): Promise<ConfirmResponse> {
  const res = await fetch(`${API_BASE}/api/v1/documents/${documentId}/extraction/confirm?invoice_index=${invoiceIndex}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getToken()}`,
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Could not save invoice." }));
    throw new Error(err.detail);
  }
  return res.json();
}

// --- CSV export ------------------------------------------------------------

export async function downloadCsv(startDate: string, endDate: string, language: string) {
  const params = new URLSearchParams({ start_date: startDate, end_date: endDate, language });
  const res = await fetch(`${API_BASE}/api/v1/exports/csv?${params.toString()}`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Could not generate CSV export." }));
    throw new Error(err.detail);
  }
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  const disposition = res.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="?([^"]+)"?/);
  a.download = match ? match[1] : `invoices_${language}_${startDate}_to_${endDate}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

// --- Admin -------------------------------------------------------------

export interface AdminUserRow {
  id: number;
  email: string;
  full_name: string | null;
  role: string;
  plan: string;
  created_at: string;
  plan_started_at: string | null;
  subscription_status: string | null;
  documents_total: number;
  documents_this_month: number;
  invoices_this_billing_period: number;
  billing_period_limit: number;
}

export async function listAllUsers(): Promise<AdminUserRow[]> {
  const res = await fetch(`${API_BASE}/api/v1/admin/users`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!res.ok) throw new Error("Could not load users.");
  return res.json();
}

export async function updateUser(userId: number, changes: { role?: string; plan?: string }) {
  const res = await fetch(`${API_BASE}/api/v1/admin/users/${userId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getToken()}`,
    },
    body: JSON.stringify(changes),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Could not update user." }));
    throw new Error(err.detail);
  }
  return res.json();
}

export interface AdminDocumentRow {
  id: number;
  user_email: string;
  original_filename: string;
  status: string;
  language: string;
  detected_language: string | null;
  page_count: number | null;
  uploaded_at: string;
}

export async function listAllDocuments(): Promise<AdminDocumentRow[]> {
  const res = await fetch(`${API_BASE}/api/v1/admin/documents`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!res.ok) throw new Error("Could not load documents.");
  return res.json();
}

export async function deleteDocumentAdmin(documentId: number) {
  const res = await fetch(`${API_BASE}/api/v1/admin/documents/${documentId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Could not delete document." }));
    throw new Error(err.detail);
  }
  return res.json();
}

export interface AuditLogRow {
  id: number;
  admin_email: string;
  action: string;
  target_type: string;
  target_id: number;
  details: string | null;
  created_at: string;
}

export async function getAuditLog(): Promise<AuditLogRow[]> {
  const res = await fetch(`${API_BASE}/api/v1/admin/audit-log`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!res.ok) throw new Error("Could not load audit log.");
  return res.json();
}

// --- Visitor (no-login) free-tier flow --------------------------------

export function getOrCreateVisitorSessionId(): string {
  const key = "ocrdocflow_visitor_session";
  let sessionId = localStorage.getItem(key);
  if (!sessionId) {
    sessionId = crypto.randomUUID();
    localStorage.setItem(key, sessionId);
  }
  return sessionId;
}

export interface VisitorUploadResult {
  id: number;
  original_filename: string;
  status: string;
  uploaded_at: string;
  uploads_used: number;
  uploads_remaining: number;
}

export async function visitorUpload(
  file: File,
  language: string,
  email?: string
): Promise<VisitorUploadResult> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("language", language);
  formData.append("session_id", getOrCreateVisitorSessionId());
  if (email) formData.append("email", email);

  const res = await fetch(`${API_BASE}/api/v1/visitor/upload`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Upload failed." }));
    // Signal the email-required case distinctly so the UI can show the
    // right prompt instead of a generic error.
    if (res.status === 402 && err.detail === "EMAIL_REQUIRED") {
      const e = new Error("EMAIL_REQUIRED");
      throw e;
    }
    throw new Error(err.detail);
  }
  return res.json();
}

export async function listVisitorDocuments() {
  const sessionId = getOrCreateVisitorSessionId();
  const res = await fetch(`${API_BASE}/api/v1/visitor/documents?session_id=${sessionId}`);
  if (!res.ok) throw new Error("Could not load documents.");
  return res.json();
}

export async function getVisitorExtraction(documentId: number, invoiceIndex: number = 0) {
  const sessionId = getOrCreateVisitorSessionId();
  const res = await fetch(
    `${API_BASE}/api/v1/visitor/documents/${documentId}/extraction?session_id=${sessionId}&invoice_index=${invoiceIndex}`
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Could not load extracted data." }));
    throw new Error(err.detail);
  }
  return res.json();
}

export async function downloadVisitorCsv(language: string) {
  const sessionId = getOrCreateVisitorSessionId();
  const params = new URLSearchParams({ session_id: sessionId, language });
  const res = await fetch(`${API_BASE}/api/v1/visitor/csv?${params.toString()}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Could not generate CSV." }));
    throw new Error(err.detail);
  }
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "ocrdocflow_free_trial.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

// --- Billing / Stripe -------------------------------------------------

export interface PlanInfo {
  name: string;
  price_usd: number;
  invoices_per_month: number;
  // Present only while the launch promotion is running.
  promo_price_usd?: number;
}

export interface PromoInfo {
  name: string;
  percent_off: number;
  seats_total: number;
  seats_left: number;
  duration: "forever" | "once" | "repeating";
  duration_in_months: number | null;
  ends_at: string | null; // ISO date, or null when there is no end date
}

export interface PlansResponse {
  plans: Record<string, PlanInfo>;
  promo: PromoInfo | null;
}

export async function getPlans(): Promise<PlansResponse> {
  const res = await fetch(`${API_BASE}/api/v1/billing/plans`);
  if (!res.ok) throw new Error("Could not load plans.");
  return res.json();
}

export async function createCheckoutSession(plan: string): Promise<string> {
  const res = await fetch(`${API_BASE}/api/v1/billing/create-checkout-session`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getToken()}`,
    },
    body: JSON.stringify({ plan }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Could not start checkout." }));
    throw new Error(err.detail);
  }
  const data = await res.json();
  return data.checkout_url;
}


// --- Organization -------------------------------------------------


// --- Organization / Team management -------------------------------------

export interface MyOrganization {
  id: number;
  name: string;
  plan: string;
  max_members: number;
  member_count: number;
  my_role: string;
}

export async function getMyOrganization(): Promise<MyOrganization> {
  const res = await fetch(`${API_BASE}/api/v1/organization/me`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Could not load organization." }));
    throw new Error(err.detail);
  }
  return res.json();
}

export interface OrgMember {
  id: number;
  email: string;
  full_name: string | null;
  org_role: string;
}

export async function listOrgMembers(): Promise<OrgMember[]> {
  const res = await fetch(`${API_BASE}/api/v1/organization/members`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Could not load members." }));
    throw new Error(err.detail);
  }
  return res.json();
}

export async function inviteMember(email: string) {
  const res = await fetch(`${API_BASE}/api/v1/organization/invite`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getToken()}`,
    },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Could not add member." }));
    throw new Error(err.detail);
  }
  return res.json();
}

export async function removeMember(userId: number) {
  const res = await fetch(`${API_BASE}/api/v1/organization/members/${userId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Could not remove member." }));
    throw new Error(err.detail);
  }
  return res.json();
}
