import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  getToken, getMyOrganization, listOrgMembers, inviteMember, removeMember,
  MyOrganization, OrgMember,
} from "../api";

export default function TeamPage() {
  const [org, setOrg] = useState<MyOrganization | null>(null);
  const [members, setMembers] = useState<OrgMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviting, setInviting] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    if (!getToken()) {
      navigate("/login");
      return;
    }
    loadAll();
  }, []);

  async function loadAll() {
    setLoading(true);
    setError("");
    try {
      const [orgData, membersData] = await Promise.all([getMyOrganization(), listOrgMembers()]);
      setOrg(orgData);
      setMembers(membersData);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleInvite() {
    if (!inviteEmail.includes("@")) {
      setError("Please enter a valid email address.");
      return;
    }
    setInviting(true);
    setError("");
    setMessage("");
    try {
      await inviteMember(inviteEmail);
      setMessage(`${inviteEmail} added to your team.`);
      setInviteEmail("");
      await loadAll();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setInviting(false);
    }
  }

  async function handleRemove(userId: number, email: string) {
    if (!window.confirm(`Remove ${email} from your team? They'll get their own free solo account.`)) {
      return;
    }
    setError("");
    setMessage("");
    try {
      await removeMember(userId);
      setMessage(`${email} removed from your team.`);
      await loadAll();
    } catch (err: any) {
      setError(err.message);
    }
  }

  if (loading) {
    return <div className="min-h-screen bg-gray-50 p-8">Loading...</div>;
  }

  const isOwner = org?.my_role === "owner";

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-2xl mx-auto">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold">Team</h1>
          <button onClick={() => navigate("/dashboard")} className="text-sm text-gray-600 hover:underline">
            ← Back to Dashboard
          </button>
        </div>

        {error && <p className="text-sm text-red-600 mb-3">{error}</p>}
        {message && <p className="text-sm text-blue-700 mb-3">{message}</p>}

        {org && (
          <div className="bg-white rounded-lg shadow p-4 mb-4">
            <p className="text-sm text-gray-500">
              <span className="font-semibold text-gray-800">{org.name}</span>
              {" · "}
              <span className="capitalize">{org.plan}</span> plan
              {" · "}
              {org.member_count} / {org.max_members} member{org.max_members === 1 ? "" : "s"}
            </p>
          </div>
        )}

        {isOwner && org && org.member_count < org.max_members && (
          <div className="bg-white rounded-lg shadow p-4 mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Add a team member
            </label>
            <p className="text-xs text-gray-500 mb-2">
              They need to already have a free OCRDocFlow account with this email - once they do,
              adding them here moves them onto your team's plan.
            </p>
            <div className="flex gap-2">
              <input
                type="email"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="teammate@example.com"
                className="flex-1 border rounded px-3 py-2 text-sm"
              />
              <button
                onClick={handleInvite}
                disabled={inviting}
                className="px-4 py-2 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 text-sm"
              >
                {inviting ? "Adding..." : "Add"}
              </button>
            </div>
          </div>
        )}

        {isOwner && org && org.member_count >= org.max_members && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4 text-sm text-amber-800">
            Your {org.plan} plan is at its member limit ({org.max_members}).{" "}
            <button onClick={() => navigate("/billing")} className="font-semibold underline">
              Upgrade your plan
            </button>{" "}
            to add more team members.
          </div>
        )}

        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="p-4 font-semibold text-gray-800 border-b">
            Members ({members.length})
          </div>
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-100">
              <tr>
                <th className="p-3">Email</th>
                <th className="p-3">Name</th>
                <th className="p-3">Role</th>
                {isOwner && <th className="p-3"></th>}
              </tr>
            </thead>
            <tbody>
              {members.map((m) => (
                <tr key={m.id} className="border-t">
                  <td className="p-3">{m.email}</td>
                  <td className="p-3">{m.full_name || "—"}</td>
                  <td className="p-3 capitalize">{m.org_role}</td>
                  {isOwner && (
                    <td className="p-3">
                      {m.org_role !== "owner" && (
                        <button
                          onClick={() => handleRemove(m.id, m.email)}
                          className="text-red-600 hover:underline text-xs"
                        >
                          Remove
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

