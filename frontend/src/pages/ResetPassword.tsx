import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { resetPassword } from "../api";

const MIN_LENGTH = 8;

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (password.length < MIN_LENGTH) {
      setError(`Password must be at least ${MIN_LENGTH} characters.`);
      return;
    }
    if (password !== confirm) {
      setError("The two passwords are not the same.");
      return;
    }
    setSaving(true);
    try {
      setDone(await resetPassword(token, password));
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <form onSubmit={handleSubmit} className="bg-white p-8 rounded-lg shadow-md w-full max-w-sm">
        <h1 className="text-2xl font-bold mb-6 text-center">Choose a new password</h1>
        {!token ? (
          <p className="text-sm text-red-600 mb-4">
            This page needs the link from the reset email.{" "}
            <Link to="/forgot-password" className="text-blue-600">Request a new link</Link>.
          </p>
        ) : done ? (
          <>
            <p className="text-sm text-green-700 bg-green-50 border border-green-200 rounded p-3 mb-4">{done}</p>
            <Link to="/login" className="block w-full text-center bg-blue-600 text-white rounded py-2 hover:bg-blue-700">
              Log In
            </Link>
          </>
        ) : (
          <>
            {error && (
              <p className="text-red-600 text-sm mb-4">
                {error}{" "}
                {error.includes("link") && (
                  <Link to="/forgot-password" className="text-blue-600 underline">Request a new link</Link>
                )}
              </p>
            )}
            <input
              type="password"
              placeholder={`New password (at least ${MIN_LENGTH} characters)`}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full border rounded px-3 py-2 mb-4"
              autoComplete="new-password"
              required
            />
            <input
              type="password"
              placeholder="Repeat new password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className="w-full border rounded px-3 py-2 mb-4"
              autoComplete="new-password"
              required
            />
            <button
              type="submit"
              disabled={saving}
              className="w-full bg-blue-600 text-white rounded py-2 hover:bg-blue-700 disabled:opacity-60"
            >
              {saving ? "Saving..." : "Save new password"}
            </button>
          </>
        )}
      </form>
    </div>
  );
}
