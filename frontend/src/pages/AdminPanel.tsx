import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  getMe, getToken, CurrentUser,
  listAllUsers, updateUser, AdminUserRow,
  listAllDocuments, deleteDocumentAdmin, AdminDocumentRow,
  getAuditLog, AuditLogRow,
} from "../api";
import SortableFilterTable, { ColumnDef } from "../components/SortableFilterTable";

const ROLES = ["user", "admin"];
const PLANS = ["free", "starter", "professional", "business"];

type Tab = "users" | "documents" | "audit";

export default function AdminPanel() {
  const [checking, setChecking] = useState(true);
  const [authorized, setAuthorized] = useState(false);
  const [tab, setTab] = useState<Tab>("users");

  const [users, setUsers] = useState<AdminUserRow[]>([]);
  const [docs, setDocs] = useState<AdminDocumentRow[]>([]);
  const [auditLog, setAuditLog] = useState<AuditLogRow[]>([]);

  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    if (!getToken()) {
      navigate("/login");
      return;
    }
    // Frontend check is just for a clean redirect/UX - the backend
    // independently enforces real access control on every admin
    // endpoint (Security Policy Section 7).
    getMe()
      .then((me: CurrentUser) => {
        if (me.role !== "admin") {
          navigate("/dashboard");
          return null;
        }
        setAuthorized(true);
        return loadAll();
      })
      .catch((err) => setError(err.message))
      .finally(() => setChecking(false));
  }, []);

  async function loadAll() {
    const [u, d, a] = await Promise.all([listAllUsers(), listAllDocuments(), getAuditLog()]);
    setUsers(u);
    setDocs(d);
    setAuditLog(a);
  }

  async function handleRoleChange(userId: number, role: string) {
    setError("");
    try {
      await updateUser(userId, { role });
      setMessage("Role updated.");
      await loadAll();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function handlePlanChange(userId: number, plan: string) {
    setError("");
    try {
      await updateUser(userId, { plan });
      setMessage("Plan updated.");
      await loadAll();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function handleDeleteDocument(docId: number, filename: string) {
    if (!window.confirm(`Delete "${filename}"? This removes the file, its OCR data, and any saved invoice. This cannot be undone.`)) {
      return;
    }
    setError("");
    try {
      await deleteDocumentAdmin(docId);
      setMessage("Document deleted.");
      await loadAll();
    } catch (err: any) {
      setError(err.message);
    }
  }

  if (checking) {
    return <div className="min-h-screen bg-gray-50 p-8">Loading...</div>;
  }
  if (!authorized) {
    return null; // navigate() above already redirected away
  }

  const userColumns: ColumnDef<AdminUserRow>[] = [
    { key: "id", label: "ID" },
    { key: "email", label: "Email", filterType: "text" },
    { key: "full_name", label: "Full Name", filterType: "text" },
    {
      key: "role",
      label: "Role",
      filterType: "select",
      render: (u) => (
        <select
          value={u.role}
          onChange={(e) => handleRoleChange(u.id, e.target.value)}
          className="border rounded px-2 py-1 text-xs"
        >
          {ROLES.map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>
      ),
    },
    {
      key: "plan",
      label: "Plan",
      filterType: "select",
      render: (u) => (
        <select
          value={u.plan}
          onChange={(e) => handlePlanChange(u.id, e.target.value)}
          className="border rounded px-2 py-1 text-xs"
        >
          {PLANS.map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
      ),
    },
    { key: "documents_this_month", label: "This Month" },
    { key: "documents_total", label: "Total Docs" },
    {
      key: "usage",
      label: "Billing Period Usage",
      getValue: (u) => u.invoices_this_billing_period,
      render: (u) => {
        const pct = u.billing_period_limit > 0
          ? Math.round((u.invoices_this_billing_period / u.billing_period_limit) * 100)
          : 0;
        const color = pct >= 100 ? "text-red-600" : pct >= 90 ? "text-amber-600" : "text-gray-700";
        return (
          <span className={color}>
            {u.invoices_this_billing_period} / {u.billing_period_limit} ({pct}%)
          </span>
        );
      },
    },
    {
      key: "created_at",
      label: "Joined",
      getValue: (u) => new Date(u.created_at).getTime(),
      render: (u) => new Date(u.created_at).toLocaleDateString(),
    },
    {
      key: "plan_started_at",
      label: "Plan Started",
      getValue: (u) => (u.plan_started_at ? new Date(u.plan_started_at).getTime() : 0),
      render: (u) =>
        u.plan_started_at
          ? new Date(u.plan_started_at).toLocaleDateString()
          : <span className="text-gray-400">— (never subscribed)</span>,
    },
  ];

  const documentColumns: ColumnDef<AdminDocumentRow>[] = [
    { key: "original_filename", label: "File", filterType: "text" },
    { key: "user_email", label: "Uploaded By", filterType: "text" },
    { key: "status", label: "Status", filterType: "select" },
    { key: "language", label: "Language", filterType: "select" },
    { key: "page_count", label: "Pages" },
    {
      key: "uploaded_at",
      label: "Uploaded",
      getValue: (d) => new Date(d.uploaded_at).getTime(),
      render: (d) => new Date(d.uploaded_at).toLocaleString(),
    },
    {
      key: "actions",
      label: "",
      render: (d) => (
        <button
          onClick={() => handleDeleteDocument(d.id, d.original_filename)}
          className="text-red-600 hover:underline text-xs"
        >
          Delete
        </button>
      ),
    },
  ];

  const auditColumns: ColumnDef<AuditLogRow>[] = [
    {
      key: "created_at",
      label: "When",
      getValue: (l) => new Date(l.created_at).getTime(),
      render: (l) => new Date(l.created_at).toLocaleString(),
    },
    { key: "admin_email", label: "Admin", filterType: "text" },
    { key: "action", label: "Action", filterType: "select" },
    { key: "target_type", label: "Target Type", filterType: "select" },
    { key: "target_id", label: "Target ID" },
    { key: "details", label: "Details", filterType: "text" },
  ];

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-6xl mx-auto">
        <div className="flex justify-between items-center mb-4">
          <h1 className="text-2xl font-bold">Admin Panel</h1>
          <button onClick={() => navigate("/dashboard")} className="text-sm text-gray-600 hover:underline">
            ← Back to Dashboard
          </button>
        </div>

        {error && <p className="text-sm text-red-600 mb-3">{error}</p>}
        {message && <p className="text-sm text-blue-700 mb-3">{message}</p>}

        <div className="flex gap-2 mb-4">
          {(["users", "documents", "audit"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 rounded text-sm font-medium ${
                tab === t ? "bg-blue-600 text-white" : "bg-white text-gray-600 border"
              }`}
            >
              {t === "users" && `Users (${users.length})`}
              {t === "documents" && `Documents (${docs.length})`}
              {t === "audit" && `Audit Log (${auditLog.length})`}
            </button>
          ))}
        </div>

        <div className="bg-white rounded-lg shadow overflow-hidden">
          {tab === "users" && (
            <SortableFilterTable columns={userColumns} rows={users} rowKey={(u) => u.id} />
          )}
          {tab === "documents" && (
            <SortableFilterTable columns={documentColumns} rows={docs} rowKey={(d) => d.id} />
          )}
          {tab === "audit" && (
            <SortableFilterTable columns={auditColumns} rows={auditLog} rowKey={(l) => l.id} />
          )}
        </div>
      </div>
    </div>
  );
}
