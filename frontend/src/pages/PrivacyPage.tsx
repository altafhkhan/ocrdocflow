import { Link } from "react-router-dom";

// OCRDocFlow product privacy notice (website and Android/iOS apps).
//
// It sits UNDER the company policy at qumaxa.com/privacy-policy and only
// adds what is specific to this product. Every statement here describes
// what the code and the server actually do - when behaviour changes (OCR
// provider or tier, retention, a new processor), change this page and its
// version/date in the same commit. The wording needs the owner's approval
// before a new version goes live.
const VERSION = "1.1";
const EFFECTIVE = "19 November 2026";
const PRIVACY_EMAIL = "privacy@qumaxa.com";
const COMPANY_POLICY = "https://qumaxa.com/privacy-policy";

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="mb-8 scroll-mt-4">
      <h2 className="text-lg font-bold text-gray-900 mb-2">{title}</h2>
      <div className="space-y-3 text-sm leading-6 text-gray-700">{children}</div>
    </section>
  );
}

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-gray-50 p-4 sm:p-8">
      <div className="max-w-3xl mx-auto bg-white rounded-lg shadow p-6 sm:p-10">
        <p className="text-sm mb-4">
          <Link to="/" className="text-blue-600 hover:underline">← Back to OCRDocFlow</Link>
        </p>
        <h1 className="text-2xl font-bold mb-1">OCRDocFlow Privacy Notice</h1>
        <p className="text-xs text-gray-500 mb-6">
          Version {VERSION} · effective {EFFECTIVE} · applies to ocrdocflow.qumaxa.com and the OCRDocFlow
          Android and iOS apps
        </p>

        <Section id="who" title="1. Who we are">
          <p>
            OCRDocFlow is a product of QUMAXA IT SERVICES (SMC-PRIVATE) LIMITED, Johar Block-20,
            Gulshan-e-Iqbal Town, Karachi East, Karachi, Pakistan (“Qumaxa”, “we”). This notice explains
            what OCRDocFlow does with your information. It adds to the{" "}
            <a href={COMPANY_POLICY} className="text-blue-600 underline">Qumaxa Privacy Policy</a>, which
            also applies.
          </p>
        </Section>

        <Section id="collect" title="2. What we collect">
          <ul className="list-disc pl-5 space-y-2">
            <li>
              <strong>Account details:</strong> your email address, your name if you give it, and your
              password (stored only in scrambled, hashed form). Team members you invite are stored the same way.
            </li>
            <li>
              <strong>Documents you upload:</strong> the invoice or voucher files (PDF, JPG, PNG), including
              photos you take with the app's camera button, the text read from them, and the invoice details
              extracted from them (for example supplier or customer names, dates, line items and totals).
              These documents may contain personal information about other people; you are responsible for
              having the right to upload them.
            </li>
            <li>
              <strong>Usage records:</strong> when each document was uploaded, how many invoices it counted
              as, the AI model used, and the estimated processing cost. We use these for plan limits and
              cost control.
            </li>
            <li>
              <strong>Technical data:</strong> your IP address with each upload, and server logs.
            </li>
            <li>
              <strong>Free trial without an account:</strong> your IP address, a random identifier kept in
              your browser or app, the number of uploads, and your email address if you choose to give it
              to continue the trial.
            </li>
            <li>
              <strong>Subscription details:</strong> your plan and its status. Card details are entered on
              Stripe's own payment page and never reach us.
            </li>
          </ul>
          <p>
            The apps do not collect your location, contacts, advertising identifier or device identifiers,
            and contain no advertising or analytics trackers. The camera is used only when you tap “Take a
            photo of the invoice”, and only that photo is uploaded.
          </p>
        </Section>

        <Section id="use" title="3. How we use it">
          <ul className="list-disc pl-5 space-y-2">
            <li>to read your documents and show you the extracted invoice data for review and export;</li>
            <li>to sign you in, apply your plan's limits, and keep the service secure and within cost limits;</li>
            <li>to send service emails such as password-reset links;</li>
            <li>to contact a free-trial visitor who gave an email address about the product.</li>
          </ul>
          <p>We do not sell your information and we do not use your documents for advertising.</p>
        </Section>

        <Section id="ai" title="4. AI processing of your documents">
          <p>
            To read a document, OCRDocFlow sends the file to Google's Gemini API, which returns the text and
            the invoice fields. If that service is unavailable, the document is read by software running on
            our own server instead.
          </p>
          <p>
            <strong>Important during the free beta:</strong> we currently use Google's standard, unpaid
            Gemini API tier. Under Google's terms for that tier, Google may use submitted content to
            improve its products, and human reviewers at Google may see it. Please do not upload documents
            that you are not permitted to share on that basis. We will update this notice when we move to a
            paid tier, under which Google does not use submitted content to train its models.
          </p>
          <p>We do not use your documents to train any model of our own.</p>
        </Section>

        <Section id="share" title="5. Who else handles your information">
          <p>We use these service providers to run OCRDocFlow:</p>
          <ul className="list-disc pl-5 space-y-2">
            <li><strong>Google (Gemini API)</strong> — reading documents, as described above.</li>
            <li><strong>DigitalOcean</strong> — the server that runs the service and stores uploaded files.</li>
            <li><strong>Neon</strong> — the managed database holding accounts and extracted invoice data.</li>
            <li><strong>Stripe</strong> — subscription payments.</li>
            <li><strong>Our email provider</strong> — delivering password-reset and service emails.</li>
          </ul>
          <p>
            These providers may process information outside Pakistan and outside your own country. Members
            of your own organization in OCRDocFlow can see the documents and invoices of that organization.
            Authorised Qumaxa staff can access accounts and documents for support, security and
            administration; such administrative actions are logged. We disclose information where the law
            requires it.
          </p>
        </Section>

        <Section id="keep" title="6. How long we keep it">
          <ul className="list-disc pl-5 space-y-2">
            <li>
              <strong>On a paid plan:</strong> your documents and invoice records are kept until your
              current subscription period closes. From the day after it closes they are due for deletion
              from our servers and may be removed at any time. This applies when you continue your
              subscription into the next period as well, so download your invoices (CSV or Excel) before
              each period ends. Your account itself is not deleted.
            </li>
            <li>
              <strong>On the free plan:</strong> your documents and extracted data are kept until you ask
              us to delete them or your account is closed.
            </li>
            <li>
              <strong>Free trial without an account:</strong> uploaded files and their extracted data are
              deleted automatically about 24 hours after upload (the clean-up runs when the trial is next
              used). The record of how many uploads came from an IP address, and any email address given,
              is kept to operate the trial limit.
            </li>
            <li>
              <strong>In the app:</strong> a sign-in token is stored on your device so you stay signed in
              for up to 30 days. Export files you download are placed in the app's temporary storage so you
              can share them. Uninstalling the app removes both.
            </li>
          </ul>
        </Section>

        <Section id="delete" title="7. Deleting your account or your data">
          <p>
            To delete your OCRDocFlow account, or particular documents, email{" "}
            <a href={`mailto:${PRIVACY_EMAIL}?subject=OCRDocFlow%20deletion%20request`} className="text-blue-600 underline">
              {PRIVACY_EMAIL}
            </a>{" "}
            from the email address of the account and say what you want deleted. We will delete the account,
            its uploaded files and its extracted invoice data within 30 days and confirm by email. If the
            account owns an organization with other members, tell us whether the organization should be
            deleted too. We may keep limited records where the law requires it, such as payment records.
          </p>
          <p>
            You can also ask us for a copy of your information or to correct it, using the same address.
          </p>
        </Section>

        <Section id="security" title="8. Security">
          <p>
            Connections to OCRDocFlow are encrypted (HTTPS). Passwords are stored hashed. Each account can
            only reach its own organization's documents. No system is perfectly secure; if you believe your
            account has been misused, contact us straight away.
          </p>
        </Section>

        <Section id="children" title="9. Children">
          <p>OCRDocFlow is a business tool and is not intended for anyone under 18.</p>
        </Section>

        <Section id="changes" title="10. Changes to this notice">
          <p>
            When what OCRDocFlow does with information changes, we will update this page and its version and
            date above.
          </p>
        </Section>

        <Section id="contact" title="11. Contact">
          <p>
            Privacy questions and requests:{" "}
            <a href={`mailto:${PRIVACY_EMAIL}`} className="text-blue-600 underline">{PRIVACY_EMAIL}</a>.
            Postal address: QUMAXA IT SERVICES (SMC-PRIVATE) LIMITED, Johar Block-20, Gulshan-e-Iqbal Town,
            Karachi East, Karachi, Pakistan.
          </p>
        </Section>
      </div>
    </div>
  );
}
