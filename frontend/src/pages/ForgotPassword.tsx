import { useState } from "react";
import { Link } from "react-router-dom";
import { requestPasswordReset } from "../api";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSending(true);
    try {
      setMessage(await requestPasswordReset(email));
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <form onSubmit={handleSubmit} className="bg-white p-8 rounded-lg shadow-md w-full max-w-sm">
        <h1 className="text-2xl font-bold mb-2 text-center">Forgot your password?</h1>
        {message ? (
          <>
            <p className="text-sm text-green-700 bg-green-50 border border-green-200 rounded p-3 my-4">{message}</p>
            <p className="text-sm text-gray-600">
              Check your inbox and your spam folder. No email after a few minutes? Write to{" "}
              <a href="mailto:altaf.khan@qumaxa.com" className="text-blue-600">altaf.khan@qumaxa.com</a>.
            </p>
          </>
        ) : (
          <>
            <p className="text-sm text-gray-600 mb-6 text-center">
              Enter the email of your account and we will send you a link to choose a new password.
            </p>
            {error && <p className="text-red-600 text-sm mb-4">{error}</p>}
            <input
              type="email"
              name="email"
              autoComplete="username"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full border rounded px-3 py-2 mb-4"
              required
            />
            <button
              type="submit"
              disabled={sending}
              className="w-full bg-blue-600 text-white rounded py-2 hover:bg-blue-700 disabled:opacity-60"
            >
              {sending ? "Sending..." : "Send reset link"}
            </button>
          </>
        )}
        <p className="text-sm text-center mt-4">
          <Link to="/login" className="text-blue-600">Back to Log In</Link>
        </p>
      </form>
    </div>
  );
}
