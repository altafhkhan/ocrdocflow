import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getMe, getPlans, createCheckoutSession, getToken, CurrentUser, PlanInfo } from "../api";

export default function BillingPage() {
  const [me, setMe] = useState<CurrentUser | null>(null);
  const [plans, setPlans] = useState<Record<string, PlanInfo>>({});
  const [loading, setLoading] = useState(true);
  const [subscribing, setSubscribing] = useState<string | null>(null);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    if (!getToken()) {
      navigate("/login");
      return;
    }
    Promise.all([getMe(), getPlans()])
      .then(([meData, plansData]) => {
        setMe(meData);
        setPlans(plansData);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleSubscribe(planKey: string) {
    setSubscribing(planKey);
    setError("");
    try {
      const checkoutUrl = await createCheckoutSession(planKey);
      // Send the browser to Stripe's own hosted payment page - card
      // details are entered there, never on our site.
      window.location.href = checkoutUrl;
    } catch (err: any) {
      setError(err.message);
      setSubscribing(null);
    }
  }

  if (loading) {
    return <div className="min-h-screen bg-gray-50 p-8">Loading...</div>;
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold">Choose a Plan</h1>
          <button onClick={() => navigate("/dashboard")} className="text-sm text-gray-600 hover:underline">
            ← Back to Dashboard
          </button>
        </div>

        {error && <p className="text-sm text-red-600 mb-4">{error}</p>}

        <p className="text-sm text-gray-500 mb-6">
          Your current plan: <span className="font-semibold capitalize">{me?.role === "admin" ? "Admin (unlimited)" : "—"}</span>
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Object.entries(plans).map(([key, plan]) => (
            <div key={key} className="bg-white rounded-lg shadow p-6 flex flex-col">
              <h2 className="text-lg font-bold mb-1">{plan.name}</h2>
              <p className="text-3xl font-bold mb-1">
                ${plan.price_usd}
                <span className="text-sm font-normal text-gray-500">/month</span>
              </p>
              <p className="text-sm text-gray-500 mb-4">
                Up to {plan.invoices_per_month.toLocaleString()} invoices/month
              </p>
              <button
                onClick={() => handleSubscribe(key)}
                disabled={subscribing !== null}
                className="mt-auto px-4 py-2 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 text-sm font-medium"
              >
                {subscribing === key ? "Redirecting to checkout..." : `Subscribe to ${plan.name}`}
              </button>
            </div>
          ))}
        </div>

        <p className="text-xs text-gray-400 mt-6 text-center">
          Payments are processed securely by Stripe. We never see or store your card details.
        </p>
      </div>
    </div>
  );
}
