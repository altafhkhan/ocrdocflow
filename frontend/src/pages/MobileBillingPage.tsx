import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getMe, getToken, CurrentUser } from "../api";
import { openExternal, WEBSITE_URL } from "../native";

/**
 * The Billing screen inside the Android/iOS apps.
 *
 * The apps are sign-in only: they show the current plan and usage but sell
 * nothing, so no Apple or Google in-app purchase (and no store commission)
 * is involved. Plans are bought on the website, in the phone's browser.
 * The website keeps using BillingPage.tsx.
 */
export default function MobileBillingPage() {
  const [me, setMe] = useState<CurrentUser | null>(null);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    if (!getToken()) {
      navigate("/login");
      return;
    }
    getMe().then(setMe).catch((err) => setError(err.message));
  }, []);

  const hasUsage =
    me && typeof me.invoices_this_period === "number" && typeof me.billing_period_limit === "number";

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-md mx-auto">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold">Your plan</h1>
          <button onClick={() => navigate("/dashboard")} className="text-sm text-gray-600 hover:underline">
            ← Back
          </button>
        </div>

        {error && <p className="text-sm text-red-600 mb-4">{error}</p>}

        <div className="bg-white rounded-lg shadow p-6">
          <p className="text-sm text-gray-500">Current plan</p>
          <p className="text-xl font-bold capitalize mb-4">
            {me ? (me.role === "admin" ? "Admin (unlimited)" : me.plan) : "…"}
          </p>
          {hasUsage && (
            <p className="text-sm text-gray-700 mb-4">
              Invoices used this period:{" "}
              <span className="font-semibold">
                {me!.invoices_this_period} / {me!.billing_period_limit}
              </span>
            </p>
          )}
          <p className="text-xs text-gray-500">
            Each invoice in an uploaded file counts once. An invoice with more than 25 line items counts
            as 1 invoice for every 25 line items (for example, an invoice with 100 line items counts as 4).
          </p>
        </div>

        <div className="bg-white rounded-lg shadow p-6 mt-4">
          <p className="text-sm text-gray-700 mb-4">
            Plans cannot be bought or changed in this app. Your plan is managed in your account on the
            OCRDocFlow website.
          </p>
          <button
            onClick={() => openExternal(`${WEBSITE_URL}/billing`)}
            className="w-full px-4 py-2 rounded border border-blue-600 text-blue-700 text-sm font-medium"
          >
            Open ocrdocflow.qumaxa.com
          </button>
        </div>
      </div>
    </div>
  );
}
