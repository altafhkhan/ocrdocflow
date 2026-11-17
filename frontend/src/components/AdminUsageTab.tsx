import { useEffect, useState } from "react";
import { getUsageReport, updateOrganizationLimits, UsageReport, UsageOrgRow, UsageTotals } from "../api";

// AI usage and cost per customer for the current calendar month, with the
// limits an admin can set for each one. Costs are estimates: the tokens the
// AI provider reported x the price list configured on the server.

function money(value: number) {
  return `$${value.toFixed(value !== 0 && value < 1 ? 4 : 2)}`;
}

function CapBar({ percent }: { percent: number | null }) {
  if (percent === null) return <span className="text-xs text-gray-400">no cap</span>;
  const shown = Math.min(100, percent);
  const colour = percent >= 100 ? "bg-red-500" : percent >= 80 ? "bg-amber-500" : "bg-green-500";
  return (
    <div className="flex items-center gap-2 min-w-[110px]">
      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full ${colour}`} style={{ width: `${shown}%` }} />
      </div>
      <span className={`text-xs tabular-nums ${percent >= 100 ? "text-red-600 font-semibold" : "text-gray-600"}`}>
        {percent.toFixed(0)}%
      </span>
    </div>
  );
}

function StatCard({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="bg-gray-50 rounded-lg p-3">
      <p className="text-xs text-gray-500">{label}</p>
      <p className="text-xl font-semibold text-gray-900 tabular-nums">{value}</p>
      {note && <p className="text-xs text-gray-500 mt-0.5">{note}</p>}
    </div>
  );
}

function LimitEditor({
  org, onSaved, onError,
}: { org: UsageOrgRow; onSaved: (message: string) => void; onError: (message: string) => void }) {
  const [cap, setCap] = useState(org.cost_cap_is_custom ? String(org.cost_cap_usd) : "");
  const [limit, setLimit] = useState(org.invoice_limit_is_custom ? String(org.invoice_limit) : "");
  const [saving, setSaving] = useState(false);

  async function save() {
    const capValue = cap.trim() === "" ? null : Number(cap);
    const limitValue = limit.trim() === "" ? null : Number(limit);
    if ((capValue !== null && (Number.isNaN(capValue) || capValue < 0)) ||
        (limitValue !== null && (!Number.isInteger(limitValue) || limitValue < 0))) {
      onError("Enter a positive number, or leave the box empty to use the plan default.");
      return;
    }
    setSaving(true);
    try {
      await updateOrganizationLimits(org.id, {
        monthly_cost_cap_usd: capValue,
        invoice_limit_override: limitValue,
      });
      onSaved(`Limits saved for ${org.name}.`);
    } catch (err: any) {
      onError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex items-center gap-2">
      <label className="text-xs text-gray-500">
        Cap $
        <input
          value={cap}
          onChange={(e) => setCap(e.target.value)}
          placeholder="plan"
          inputMode="decimal"
          aria-label={`Monthly AI spending cap in dollars for ${org.name}`}
          className="ml-1 w-16 border rounded px-1.5 py-1 text-sm text-gray-900"
        />
      </label>
      <label className="text-xs text-gray-500">
        Invoices
        <input
          value={limit}
          onChange={(e) => setLimit(e.target.value)}
          placeholder="plan"
          inputMode="numeric"
          aria-label={`Invoice limit per billing period for ${org.name}`}
          className="ml-1 w-20 border rounded px-1.5 py-1 text-sm text-gray-900"
        />
      </label>
      <button
        onClick={save}
        disabled={saving}
        className="px-2.5 py-1 rounded bg-blue-600 text-white text-xs hover:bg-blue-700 disabled:opacity-50"
      >
        {saving ? "Saving..." : "Save"}
      </button>
    </div>
  );
}

function totalsNote(t: UsageTotals) {
  return `${t.documents.toLocaleString()} uploads, ${t.pages.toLocaleString()} pages`;
}

export default function AdminUsageTab() {
  const [report, setReport] = useState<UsageReport | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function load() {
    try {
      setReport(await getUsageReport());
      setError("");
    } catch (err: any) {
      setError(err.message);
    }
  }

  useEffect(() => { load(); }, []);

  if (error && !report) return <p className="p-4 text-sm text-red-600">{error}</p>;
  if (!report) return <p className="p-4 text-sm text-gray-500">Loading usage...</p>;

  const { platform, visitors, settings } = report;
  const month = new Date(report.month_start).toLocaleDateString(undefined, { month: "long", year: "numeric" });

  return (
    <div className="p-4">
      <div className="flex justify-between items-baseline mb-3">
        <h2 className="font-semibold text-gray-800">AI usage and cost, {month}</h2>
        <button onClick={load} className="text-xs text-blue-600 hover:underline">Refresh</button>
      </div>

      {error && <p className="text-sm text-red-600 mb-3">{error}</p>}
      {message && <p className="text-sm text-blue-700 mb-3">{message}</p>}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <StatCard label="Platform AI cost this month" value={money(platform.cost_usd)} note={totalsNote(platform)} />
        <StatCard
          label="Platform monthly cap"
          value={platform.cost_cap_usd > 0 ? money(platform.cost_cap_usd) : "No cap"}
          note={platform.cost_cap_used_percent !== null ? `${platform.cost_cap_used_percent}% used` : "Set PLATFORM_MONTHLY_COST_CAP_USD"}
        />
        <StatCard
          label="Tokens this month"
          value={(platform.input_tokens + platform.output_tokens).toLocaleString()}
          note={`${platform.input_tokens.toLocaleString()} in, ${platform.output_tokens.toLocaleString()} out`}
        />
        <StatCard label="Free visitors" value={money(visitors.cost_usd)} note={totalsNote(visitors)} />
      </div>

      <div className="overflow-x-auto border rounded-lg">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-left text-xs text-gray-500">
            <tr>
              <th className="px-3 py-2">Customer</th>
              <th className="px-3 py-2">Plan</th>
              <th className="px-3 py-2 text-right">Uploads</th>
              <th className="px-3 py-2 text-right">Pages</th>
              <th className="px-3 py-2 text-right">Invoices used / limit</th>
              <th className="px-3 py-2 text-right">Tokens in / out</th>
              <th className="px-3 py-2 text-right">AI cost</th>
              <th className="px-3 py-2">Of monthly cap</th>
              <th className="px-3 py-2">Set limits (empty = plan default)</th>
            </tr>
          </thead>
          <tbody>
            {report.organizations.map((org) => (
              <tr key={org.id} className="border-t align-middle">
                <td className="px-3 py-2">
                  <div className="font-medium text-gray-900">{org.name}</div>
                  <div className="text-xs text-gray-500">
                    {org.owner_email ?? "no members"}{org.members > 1 ? ` + ${org.members - 1} more` : ""}
                  </div>
                </td>
                <td className="px-3 py-2 capitalize">{org.plan}</td>
                <td className="px-3 py-2 text-right tabular-nums">{org.documents.toLocaleString()}</td>
                <td className="px-3 py-2 text-right tabular-nums">{org.pages.toLocaleString()}</td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {org.invoices_this_billing_period.toLocaleString()} / {org.invoice_limit.toLocaleString()}
                  {org.invoice_limit_is_custom && <span className="text-xs text-purple-600"> custom</span>}
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-xs text-gray-600">
                  {org.input_tokens.toLocaleString()} / {org.output_tokens.toLocaleString()}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {money(org.cost_usd)}
                  <div className="text-xs text-gray-500">
                    of {org.cost_cap_usd > 0 ? money(org.cost_cap_usd) : "no cap"}
                    {org.cost_cap_is_custom && <span className="text-purple-600"> custom</span>}
                  </div>
                </td>
                <td className="px-3 py-2"><CapBar percent={org.cost_cap_used_percent} /></td>
                <td className="px-3 py-2">
                  <LimitEditor
                    key={`${org.id}-${org.cost_cap_usd}-${org.invoice_limit}-${org.cost_cap_is_custom}-${org.invoice_limit_is_custom}`}
                    org={org}
                    onSaved={(m) => { setMessage(m); setError(""); load(); }}
                    onError={(m) => { setError(m); setMessage(""); }}
                  />
                </td>
              </tr>
            ))}
            {report.organizations.length === 0 && (
              <tr><td colSpan={9} className="px-3 py-6 text-center text-gray-500">No customers yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <ul className="mt-4 text-xs text-gray-500 space-y-1 list-disc pl-5">
        <li>
          AI cost is an estimate: tokens reported by the AI provider multiplied by the price list set on the
          server ({settings.ai_prices_usd_per_million_tokens.split(",").length} models, main model {settings.ai_model}).
          Update the price list when the provider changes its prices.
        </li>
        <li>
          Spending caps run per calendar month. A customer that reaches its cap cannot upload until next month
          or until you raise the cap here. "Invoices used" follows the customer's own billing period.
        </li>
        <li>
          An invoice with more than {settings.line_items_per_invoice} line items counts as 1 invoice for
          every {settings.line_items_per_invoice} line items.
        </li>
        <li>
          {settings.alert_email
            ? settings.alert_email_can_send
              ? `Alert emails go to ${settings.alert_email} at ${settings.alert_thresholds} of a cap.`
              : `Alert address is ${settings.alert_email}, but email sending is not configured on the server, so alerts only appear in the server log.`
            : "No alert email address is set (ALERT_EMAIL), so alerts only appear in the server log."}
        </li>
      </ul>
    </div>
  );
}
