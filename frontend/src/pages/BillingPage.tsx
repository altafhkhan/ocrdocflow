import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  getMe, getPlans, getToken, CurrentUser, PlanInfo, PromoInfo,
  startCheckout, getLoyaltyCoupon, checkCoupon, applyCouponToSubscription,
  LoyaltyPolicy, LoyaltyCoupon, LoyaltyCouponResponse,
} from "../api";

function formatDate(isoDate: string | null) {
  if (!isoDate) return "";
  return new Date(`${isoDate}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" });
}

export default function BillingPage() {
  const [me, setMe] = useState<CurrentUser | null>(null);
  const [plans, setPlans] = useState<Record<string, PlanInfo>>({});
  const [promo, setPromo] = useState<PromoInfo | null>(null);
  const [loyaltyPolicy, setLoyaltyPolicy] = useState<LoyaltyPolicy | null>(null);
  const [myCoupon, setMyCoupon] = useState<LoyaltyCouponResponse | null>(null);
  const [paymentsLive, setPaymentsLive] = useState(true);
  const [loading, setLoading] = useState(true);
  const [subscribing, setSubscribing] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  // A coupon code the visitor typed, and what the server says it is worth.
  const [couponInput, setCouponInput] = useState("");
  const [checkedCoupon, setCheckedCoupon] = useState<LoyaltyCoupon | null>(null);
  const [couponError, setCouponError] = useState("");
  const [checkingCoupon, setCheckingCoupon] = useState(false);
  const [applyingCoupon, setApplyingCoupon] = useState(false);
  const [copied, setCopied] = useState(false);
  // Checkout is ready, but the buyer must first read why their coupon was not used.
  const [pendingCheckout, setPendingCheckout] = useState<{ url: string; note: string } | null>(null);

  const navigate = useNavigate();

  useEffect(() => {
    if (!getToken()) {
      navigate("/login");
      return;
    }
    Promise.all([getMe(), getPlans()])
      .then(([meData, plansData]) => {
        setMe(meData);
        setPlans(plansData.plans);
        setPromo(plansData.promo);
        setPaymentsLive(plansData.payments_live);
        setLoyaltyPolicy(plansData.loyalty ?? null);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
    // Separate, so a problem loading the coupon never hides the plans.
    getLoyaltyCoupon().then(setMyCoupon).catch(() => setMyCoupon(null));
  }, []);

  async function handleSubscribe(planKey: string) {
    setSubscribing(planKey);
    setError("");
    setMessage("");
    try {
      const code = checkedCoupon?.code;
      const { checkout_url, discount_note } = await startCheckout(planKey, code);
      if (discount_note) {
        // Explain before leaving the page: the coupon was kept, not used.
        setPendingCheckout({ url: checkout_url, note: discount_note });
        setSubscribing(null);
        return;
      }
      // Send the browser to Stripe's own hosted payment page - card
      // details are entered there, never on our site.
      window.location.href = checkout_url;
    } catch (err: any) {
      setError(err.message);
      setSubscribing(null);
    }
  }

  async function handleCheckCoupon() {
    setCouponError("");
    setCheckedCoupon(null);
    setMessage("");
    if (!couponInput.trim()) {
      setCouponError("Please enter a coupon code.");
      return;
    }
    setCheckingCoupon(true);
    try {
      setCheckedCoupon(await checkCoupon(couponInput.trim()));
    } catch (err: any) {
      setCouponError(err.message);
    } finally {
      setCheckingCoupon(false);
    }
  }

  async function handleApplyToMySubscription(code: string) {
    setApplyingCoupon(true);
    setError("");
    setMessage("");
    try {
      const result = await applyCouponToSubscription(code);
      setMessage(result.message);
      setCheckedCoupon(null);
      setCouponInput("");
      getLoyaltyCoupon().then(setMyCoupon).catch(() => {});
    } catch (err: any) {
      setError(err.message);
    } finally {
      setApplyingCoupon(false);
    }
  }

  async function handleCopy(code: string) {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  if (loading) {
    return <div className="min-h-screen bg-gray-50 p-8">Loading...</div>;
  }

  // "for life" / "for the first 3 months" / "on your first payment"
  const promoDurationText = promo
    ? promo.duration === "forever"
      ? "for as long as you stay subscribed"
      : promo.duration === "repeating"
        ? `for your first ${promo.duration_in_months} months`
        : "on your first payment"
    : "";

  const currentPlan = me?.role === "admin" ? "Admin (unlimited)" : me?.plan ?? "—";
  const coupon = myCoupon?.coupon ?? null;
  // The launch offer beats a coupon when it is at least as big - only one applies.
  const promoBeatsCoupon = (c: LoyaltyCoupon) => !!promo && promo.percent_off >= c.percent_off;

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold">Choose a Plan</h1>
          <button onClick={() => navigate("/dashboard")} className="text-sm text-gray-600 hover:underline">
            ← Back to Dashboard
          </button>
        </div>

        {error && <p role="alert" className="text-sm text-red-600 mb-4">{error}</p>}
        {message && <p role="status" className="text-sm text-green-700 mb-4">{message}</p>}

        {pendingCheckout && (
          <div role="alert" className="mb-6 rounded-lg border border-amber-300 bg-amber-50 px-5 py-4 text-sm text-amber-900">
            <p className="font-semibold">Your coupon was not used</p>
            <p className="mt-1">{pendingCheckout.note}</p>
            <div className="mt-3 flex gap-3">
              <button
                onClick={() => { window.location.href = pendingCheckout.url; }}
                className="px-4 py-2 rounded bg-blue-600 text-white hover:bg-blue-700 text-sm font-medium"
              >
                Continue to payment
              </button>
              <button onClick={() => setPendingCheckout(null)} className="px-4 py-2 rounded border text-sm bg-white hover:bg-gray-50">
                Cancel
              </button>
            </div>
          </div>
        )}

        {!paymentsLive && (
          <div className="mb-6 rounded-lg border border-blue-200 bg-blue-50 px-5 py-4 text-sm text-blue-900">
            <p className="font-semibold">Payments open soon</p>
            <p className="mt-1">
              Online payment is not switched on yet, so the Subscribe buttons below cannot take a real card.
              To get a paid plan now, email{" "}
              <a href="mailto:altaf.khan@qumaxa.com" className="underline">altaf.khan@qumaxa.com</a>{" "}
              and we will set it up for you by hand. The launch offer still applies.
            </p>
          </div>
        )}

        {promo && (
          <div className="mb-6 rounded-lg border border-amber-300 bg-amber-50 px-5 py-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">
              Limited time offer
            </p>
            <p className="text-lg font-bold text-amber-900">
              {promo.percent_off}% off for the first {promo.seats_total} subscribers
            </p>
            <p className="text-sm text-amber-800">
              {promo.seats_left} of {promo.seats_total} spots left
              {promo.ends_at ? ` · offer ends ${promo.ends_at}` : ""}
              {" · "}discount applied automatically at checkout, {promoDurationText}.
            </p>
          </div>
        )}

        <p className="text-sm text-gray-500 mb-6">
          Your current plan: <span className="font-semibold capitalize">{currentPlan}</span>
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Object.entries(plans).map(([key, plan]) => {
            // A checked coupon lowers the price of ITS plan, unless the launch offer is bigger.
            const couponHere = checkedCoupon && checkedCoupon.plan === key && !promoBeatsCoupon(checkedCoupon) ? checkedCoupon : null;
            const couponPrice = couponHere ? Math.round(plan.price_usd * (100 - couponHere.percent_off)) / 100 : null;
            return (
              <div key={key} className="bg-white rounded-lg shadow p-6 flex flex-col">
                <div className="flex items-center justify-between mb-1">
                  <h2 className="text-lg font-bold">{plan.name}</h2>
                  {couponHere ? (
                    <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-semibold text-green-800">
                      {couponHere.percent_off}% off, {couponHere.duration_months} months
                    </span>
                  ) : promo && plan.promo_price_usd !== undefined && (
                    <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800">
                      {promo.percent_off}% off
                    </span>
                  )}
                </div>
                {couponPrice !== null ? (
                  <p className="mb-1">
                    <span className="text-lg text-gray-400 line-through mr-2">${plan.price_usd}</span>
                    <span className="text-3xl font-bold text-green-700">${couponPrice}</span>
                    <span className="text-sm font-normal text-gray-500">/month</span>
                  </p>
                ) : promo && plan.promo_price_usd !== undefined ? (
                  <p className="mb-1">
                    <span className="text-lg text-gray-400 line-through mr-2">${plan.price_usd}</span>
                    <span className="text-3xl font-bold text-amber-700">${plan.promo_price_usd}</span>
                    <span className="text-sm font-normal text-gray-500">/month</span>
                  </p>
                ) : (
                  <p className="text-3xl font-bold mb-1">
                    ${plan.price_usd}
                    <span className="text-sm font-normal text-gray-500">/month</span>
                  </p>
                )}
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
            );
          })}
        </div>

        {loyaltyPolicy && (
          <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* The offer, and the customer's own coupon */}
            <section className="bg-white rounded-lg shadow p-6">
              <p className="text-xs font-semibold uppercase tracking-wide text-green-700">Loyalty reward</p>
              <h2 className="text-lg font-bold text-gray-900 mb-2">
                {loyaltyPolicy.percent_off}% off for our customers, and for a friend
              </h2>
              <ul className="text-sm text-gray-600 space-y-1 list-disc pl-5 mb-4">
                <li>Every paying customer receives one coupon code.</li>
                <li>
                  It gives {loyaltyPolicy.percent_off}% off the plan you are on, for {loyaltyPolicy.duration_months} monthly payments.
                </li>
                <li>Use it on your own subscription, or give it to someone who is not a customer yet.</li>
                <li>
                  It stays valid until {loyaltyPolicy.valid_months_after_plan_end} months after your current plan period ends,
                  and can be used {loyaltyPolicy.max_redemptions === 1 ? "once" : `${loyaltyPolicy.max_redemptions} times`}.
                </li>
                <li>Only one discount applies at a time. While a bigger offer is running, the bigger one is used.</li>
              </ul>

              {coupon ? (
                <div className="rounded border border-green-200 bg-green-50 px-4 py-3">
                  <p className="text-xs text-green-800">Your coupon for the {coupon.plan_name} plan</p>
                  <div className="flex items-center gap-3 mt-1">
                    <span className={`font-mono text-lg font-bold tracking-wider ${coupon.usable ? "text-green-900" : "text-gray-400 line-through"}`}>
                      {coupon.code}
                    </span>
                    {coupon.usable && (
                      <button onClick={() => handleCopy(coupon.code)} className="text-xs text-blue-600 hover:underline">
                        {copied ? "Copied" : "Copy"}
                      </button>
                    )}
                  </div>
                  <p className="text-sm text-green-900 mt-1">
                    {coupon.used
                      ? "This coupon has been used."
                      : coupon.expired
                        ? `This coupon expired on ${formatDate(coupon.expires_at)}.`
                        : `${coupon.percent_off}% off for ${coupon.duration_months} months. Expires on ${formatDate(coupon.expires_at)}.`}
                  </p>
                  {coupon.usable && myCoupon?.can_apply_to_own_subscription && (
                    <button
                      onClick={() => handleApplyToMySubscription(coupon.code)}
                      disabled={applyingCoupon}
                      className="mt-3 px-3 py-1.5 rounded bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 text-sm"
                    >
                      {applyingCoupon ? "Applying..." : "Use it on my subscription"}
                    </button>
                  )}
                </div>
              ) : (
                <p className="text-sm text-gray-500">
                  {myCoupon?.reason ?? "Subscribe to a paid plan to receive your loyalty coupon."}
                </p>
              )}
            </section>

            {/* Redeeming a code someone gave you */}
            <section className="bg-white rounded-lg shadow p-6">
              <h2 className="text-lg font-bold text-gray-900 mb-2">Have a coupon code?</h2>
              <p className="text-sm text-gray-600 mb-3">
                Enter it here, then choose the plan it is for. You do not need to be a customer already.
              </p>
              <div className="flex gap-2">
                <input
                  value={couponInput}
                  onChange={(e) => { setCouponInput(e.target.value); setCheckedCoupon(null); setCouponError(""); }}
                  onKeyDown={(e) => { if (e.key === "Enter") handleCheckCoupon(); }}
                  placeholder="LOYAL-XXXXXXXX"
                  aria-label="Coupon code"
                  autoComplete="off"
                  className="flex-1 border rounded px-3 py-2 font-mono uppercase"
                />
                <button
                  onClick={handleCheckCoupon}
                  disabled={checkingCoupon}
                  className="px-4 py-2 rounded border bg-white hover:bg-gray-50 disabled:opacity-50 text-sm font-medium"
                >
                  {checkingCoupon ? "Checking..." : "Check code"}
                </button>
              </div>
              {couponError && <p role="alert" className="text-sm text-red-600 mt-2">{couponError}</p>}
              {checkedCoupon && (
                <div role="status" className="mt-3 rounded border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-900">
                  <p className="font-semibold">
                    {checkedCoupon.percent_off}% off the {checkedCoupon.plan_name} plan for {checkedCoupon.duration_months} months
                  </p>
                  <p>Valid until {formatDate(checkedCoupon.expires_at)}.</p>
                  {promoBeatsCoupon(checkedCoupon) ? (
                    <p className="mt-1 text-amber-800">
                      The launch offer ({promo?.percent_off}% off) is bigger and only one discount applies, so the launch
                      offer will be used and your coupon will be kept for later.
                    </p>
                  ) : (
                    <p className="mt-1">Now press "Subscribe to {checkedCoupon.plan_name}" above to use it.</p>
                  )}
                </div>
              )}
            </section>
          </div>
        )}

        <p className="text-xs text-gray-500 mt-6 text-center">
          Each invoice in an uploaded file counts once. An invoice with more than 25 line items counts as
          1 invoice for every 25 line items (for example, an invoice with 100 line items counts as 4).
        </p>

        <p className="text-xs text-gray-400 mt-2 text-center">
          Payments are processed securely by Stripe. We never see or store your card details.
        </p>
      </div>
    </div>
  );
}
