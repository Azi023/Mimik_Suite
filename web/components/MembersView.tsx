"use client";

import { useState, type JSX } from "react";
import {
  inviteMember,
  revokeInvite,
  updateAccountAction,
  type InviteResult,
} from "@/app/members/actions";
import type { ApiCapabilityMatrix, ApiClient, ApiInvitation, ApiUserAccount } from "@/lib/api";

interface MembersViewProps {
  accounts: ApiUserAccount[];
  invitations: ApiInvitation[];
  capabilities: ApiCapabilityMatrix;
  /** The tenant's clients — feeds the owner's per-client access editor (names, not ids). */
  clients: ApiClient[];
  /** True when the verified caller (`GET /me`) is the workspace owner — gates editing. */
  callerIsOwner: boolean;
}

type Tab = "members" | "roles" | "invites";

/** Roles a team admin may invite (client accounts are provisioned through the portal flow,
 *  super_admin is platform-only). Kept in sync with the backend invite guard. */
const INVITABLE_ROLES = ["admin", "ops", "designer"] as const;

const ROLE_LABEL: Record<string, string> = {
  super_admin: "Super admin",
  owner: "Owner",
  admin: "Admin",
  ops: "Ops",
  designer: "Designer",
  team: "Team",
  client: "Client",
  system: "System",
};

const CAP_LABEL: Record<string, string> = {
  manage_tenants: "Manage agencies",
  manage_members: "Manage members",
  manage_billing: "Billing",
  manage_clients: "Clients & brands",
  manage_creatives: "Creatives & board",
  approve_internal: "Approve",
  client_portal: "Client portal",
};

function roleLabel(role: string): string {
  return ROLE_LABEL[role] ?? role;
}

function capLabel(cap: string): string {
  return CAP_LABEL[cap] ?? cap.replace(/_/g, " ");
}

function scopeLabel(scopes: string[] | undefined): string {
  if (scopes === undefined || scopes.length === 0) return "All clients";
  return `${scopes.length} client${scopes.length === 1 ? "" : "s"}`;
}

export function MembersView({
  accounts,
  invitations,
  capabilities,
  clients,
  callerIsOwner,
}: MembersViewProps): JSX.Element {
  const [tab, setTab] = useState<Tab>("members");
  const pending = invitations.filter((i) => i.status === "pending");

  return (
    <div className="members">
      <header className="members__head">
        <div>
          <h1 className="members__title">Members &amp; roles</h1>
          <p className="members__sub">Manage who can access this workspace and what they can do.</p>
        </div>
      </header>

      <nav className="members__tabs" aria-label="Members sections">
        <TabButton id="members" active={tab} onClick={setTab} count={accounts.length}>
          Members
        </TabButton>
        <TabButton id="roles" active={tab} onClick={setTab}>
          Roles &amp; permissions
        </TabButton>
        <TabButton id="invites" active={tab} onClick={setTab} count={pending.length}>
          Invitations
        </TabButton>
      </nav>

      {tab === "members" && (
        <MembersTable accounts={accounts} clients={clients} canEdit={callerIsOwner} />
      )}
      {tab === "roles" && <RolesTable capabilities={capabilities} />}
      {tab === "invites" && <InvitesPanel pending={pending} />}
    </div>
  );
}

function TabButton({
  id,
  active,
  onClick,
  count,
  children,
}: {
  id: Tab;
  active: Tab;
  onClick: (t: Tab) => void;
  count?: number;
  children: React.ReactNode;
}): JSX.Element {
  const isActive = active === id;
  return (
    <button
      type="button"
      className={`members-tab${isActive ? " members-tab--active" : ""}`}
      aria-current={isActive ? "page" : undefined}
      onClick={() => onClick(id)}
    >
      {children}
      {count !== undefined && count > 0 && <span className="members-tab__count">{count}</span>}
    </button>
  );
}

function MembersTable({
  accounts,
  clients,
  canEdit,
}: {
  accounts: ApiUserAccount[];
  clients: ApiClient[];
  canEdit: boolean;
}): JSX.Element {
  if (accounts.length === 0) {
    return <EmptyState title="No members yet" body="Invite a teammate to get started." />;
  }
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Member</th>
            <th>Role</th>
            <th>Access</th>
            <th>Status</th>
            {canEdit && <th aria-label="Actions" />}
          </tr>
        </thead>
        <tbody>
          {accounts.map((a) => (
            <MemberRow key={a.id} account={a} clients={clients} canEdit={canEdit} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * One member row. For an OWNER caller, team rows (admin/ops/designer — the same set the
 * invite form offers) grow an Edit affordance that expands an inline editor: a role select
 * plus a per-client access checklist (nothing checked = all clients). The backend enforces
 * the actual rules; this row just surfaces its 403/404/422 answers inline.
 */
function MemberRow({
  account,
  clients,
  canEdit,
}: {
  account: ApiUserAccount;
  clients: ApiClient[];
  canEdit: boolean;
}): JSX.Element {
  // Server-action revalidation refreshes props; `saved` covers the gap so a successful
  // save reflects immediately in the row.
  const [saved, setSaved] = useState<ApiUserAccount | null>(null);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draftRole, setDraftRole] = useState<string>(account.role);
  const [draftScopes, setDraftScopes] = useState<string[]>(account.client_scopes ?? []);

  const current = saved ?? account;
  // Owner/client/system rows stay read-only — the role picker can't express them anyway.
  const editable = canEdit && (INVITABLE_ROLES as readonly string[]).includes(current.role);

  function openEditor(): void {
    setDraftRole(current.role);
    setDraftScopes(current.client_scopes ?? []);
    setError(null);
    setEditing(true);
  }

  function closeEditor(): void {
    setEditing(false);
    setError(null);
  }

  function toggleScope(clientId: string): void {
    setDraftScopes((prev) =>
      prev.includes(clientId) ? prev.filter((id) => id !== clientId) : [...prev, clientId],
    );
  }

  async function onSave(): Promise<void> {
    setBusy(true);
    setError(null);
    const res = await updateAccountAction(current.id, {
      role: draftRole,
      client_scopes: draftScopes,
    });
    setBusy(false);
    if (!res.ok || res.account === undefined) {
      setError(res.error ?? "Could not save the changes. Try again.");
      return;
    }
    setSaved(res.account);
    setEditing(false);
  }

  return (
    <>
      <tr>
        <td>
          <div className="cell-stack">
            <span className="cell-strong">{current.name ?? current.email ?? current.auth_subject}</span>
            {current.email !== null && current.name !== null && (
              <span className="cell-muted">{current.email}</span>
            )}
          </div>
        </td>
        <td>
          <span className={`role-pill role-pill--${current.role}`}>{roleLabel(current.role)}</span>
        </td>
        <td className="cell-muted">
          {current.role === "client" ? "Own client" : scopeLabel(current.client_scopes)}
        </td>
        <td>
          <span className={`status-dot status-dot--${current.active ? "on" : "off"}`}>
            {current.active ? "Active" : "Inactive"}
          </span>
        </td>
        {canEdit && (
          <td className="cell-actions">
            {editable && (
              <button
                type="button"
                className="btn-ghost"
                onClick={editing ? closeEditor : openEditor}
                disabled={busy}
              >
                {editing ? "Cancel" : "Edit"}
              </button>
            )}
          </td>
        )}
      </tr>
      {editing && (
        <tr>
          <td colSpan={5}>
            <div className="invite-form">
              <div className="invite-form__row">
                <select
                  className="input select"
                  aria-label={`Role for ${current.name ?? current.email ?? current.auth_subject}`}
                  value={draftRole}
                  onChange={(e) => setDraftRole(e.target.value)}
                  disabled={busy}
                >
                  {INVITABLE_ROLES.map((r) => (
                    <option key={r} value={r}>
                      {roleLabel(r)}
                    </option>
                  ))}
                </select>
              </div>
              <div className="cell-stack">
                <span className="invite-result__note">
                  Client access · {draftScopes.length === 0 ? "All clients" : scopeLabel(draftScopes)} —
                  leave everything unchecked for access to all clients.
                </span>
                {clients.length === 0 ? (
                  <span className="cell-muted">
                    No clients yet — this member will have access to all clients.
                  </span>
                ) : (
                  <div className="cap-chips">
                    {clients.map((c) => (
                      <label key={c.id} className="cap-chip">
                        <input
                          type="checkbox"
                          checked={draftScopes.includes(c.id)}
                          onChange={() => toggleScope(c.id)}
                          disabled={busy}
                        />{" "}
                        {c.name}
                      </label>
                    ))}
                  </div>
                )}
              </div>
              <div className="invite-form__row">
                <button type="button" className="btn-primary" onClick={onSave} disabled={busy}>
                  {busy ? "Saving…" : "Save changes"}
                </button>
                <button type="button" className="btn-ghost" onClick={closeEditor} disabled={busy}>
                  Cancel
                </button>
              </div>
              {error !== null && (
                <p className="invite-result__error" role="alert">
                  {error}
                </p>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function RolesTable({ capabilities }: { capabilities: ApiCapabilityMatrix }): JSX.Element {
  const roles = Object.keys(capabilities);
  if (roles.length === 0) {
    return (
      <EmptyState
        title="Roles unavailable"
        body="The permissions matrix could not be loaded for your account."
      />
    );
  }
  // Stable, sensible order high→low privilege.
  const order = ["super_admin", "owner", "admin", "ops", "designer", "team", "client", "system"];
  const sorted = [...roles].sort((a, b) => order.indexOf(a) - order.indexOf(b));

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Role</th>
            <th>Can do</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((role) => {
            const caps = capabilities[role] ?? [];
            return (
              <tr key={role}>
                <td>
                  <span className={`role-pill role-pill--${role}`}>{roleLabel(role)}</span>
                </td>
                <td>
                  {caps.length === 0 ? (
                    <span className="cell-muted">No capabilities</span>
                  ) : (
                    <div className="cap-chips">
                      {caps.map((c) => (
                        <span key={c} className="cap-chip">
                          {capLabel(c)}
                        </span>
                      ))}
                    </div>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function InvitesPanel({ pending }: { pending: ApiInvitation[] }): JSX.Element {
  return (
    <div className="invites">
      <InviteForm />
      {pending.length === 0 ? (
        <EmptyState title="No pending invitations" body="Invited teammates will appear here until they accept." />
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {pending.map((inv) => (
                <PendingRow key={inv.id} invitation={inv} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function PendingRow({ invitation }: { invitation: ApiInvitation }): JSX.Element {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onRevoke(): Promise<void> {
    setBusy(true);
    setError(null);
    const res = await revokeInvite(invitation.id);
    if (!res.ok) {
      setError(res.error ?? "Failed");
      setBusy(false);
    }
    // On success the server action revalidates /members and the row disappears.
  }

  return (
    <tr>
      <td className="cell-strong">{invitation.email}</td>
      <td>
        <span className={`role-pill role-pill--${invitation.role}`}>{roleLabel(invitation.role)}</span>
      </td>
      <td>
        <span className="status-dot status-dot--pending">Pending</span>
        {error !== null && <span className="cell-error"> · {error}</span>}
      </td>
      <td className="cell-actions">
        <button type="button" className="btn-ghost" onClick={onRevoke} disabled={busy}>
          {busy ? "Revoking…" : "Revoke"}
        </button>
      </td>
    </tr>
  );
}

function InviteForm(): JSX.Element {
  const [result, setResult] = useState<InviteResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  async function onSubmit(formData: FormData): Promise<void> {
    setBusy(true);
    setCopied(false);
    const res = await inviteMember(formData);
    setResult(res);
    setBusy(false);
  }

  async function copyLink(url: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <form className="invite-form" action={onSubmit}>
      <div className="invite-form__row">
        <input
          className="input"
          type="email"
          name="email"
          placeholder="teammate@agency.com"
          aria-label="Invite email"
          required
        />
        <select className="input select" name="role" aria-label="Invite role" defaultValue="ops">
          {INVITABLE_ROLES.map((r) => (
            <option key={r} value={r}>
              {roleLabel(r)}
            </option>
          ))}
        </select>
        <button type="submit" className="btn-primary" disabled={busy}>
          {busy ? "Inviting…" : "Send invite"}
        </button>
      </div>

      {result !== null && result.ok && result.acceptUrl !== undefined && (
        <div className="invite-result" role="status">
          <p className="invite-result__note">
            Invite created. Email delivery isn&apos;t wired yet — copy this link and send it:
          </p>
          <div className="invite-result__link">
            <code>{result.acceptUrl}</code>
            <button type="button" className="btn-ghost" onClick={() => copyLink(result.acceptUrl!)}>
              {copied ? "Copied ✓" : "Copy"}
            </button>
          </div>
        </div>
      )}
      {result !== null && !result.ok && (
        <p className="invite-result__error" role="alert">
          {result.error}
        </p>
      )}
    </form>
  );
}

function EmptyState({ title, body }: { title: string; body: string }): JSX.Element {
  return (
    <div className="empty-state">
      <p className="empty-state__title">{title}</p>
      <p className="empty-state__body">{body}</p>
    </div>
  );
}
