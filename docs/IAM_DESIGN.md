# IAM & Admin Panel — design proposal

> The subsystem for: invite colleagues + clients by email, assign granular access (Google-Workspace
> style), team sees everything, clients see only their own. Grounds on the existing `ActorRole`,
> `UserAccount` (tenant + role + client_id), `require_role`, and `POST /admin/accounts`. **Locking
> this model is the prerequisite** — it's load-bearing and expensive to change later.

## 1. Principals & roles (extends the existing 6)

| Role | Who | Sees | Can do |
|---|---|---|---|
| `super_admin` **(NEW)** | You (platform) | ALL agencies | Create/suspend tenants (agencies); closes the `POST /tenants` hole |
| `owner` | Agency founder | Whole tenant | Everything in the tenant: members, billing, settings, all clients |
| `admin` **(NEW)** | Senior staff | Whole tenant | Like owner minus billing/delete-tenant (manage members + all clients) |
| `ops` / `designer` | Staff | **Assigned** clients | Briefs, creatives, board moves — scoped to the clients they're assigned |
| `client` | External customer | **Own** client only | Bounded portal: view designs, approve / request-change / comment |

`team` (bootstrap) folds into `ops`. `system` stays for jobs.

## 2. The access model — role × scope (recommended)

Two independent dimensions, so "select the right access" at invite time is just two picks:

- **Role = what you can DO** (a fixed capability set per role — the matrix below).
- **Scope = which data you SEE** (which clients/projects). Internal users are either **all clients**
  in the tenant, or a **restricted set** (assigned). Clients are hard-scoped to their own `client_id`.

This covers every case you named — "team sees everything" (owner/admin = all-clients), "a designer
on only some accounts" (ops/designer = assigned scope), "clients see only their things" (client role,
own-client scope) — **without** a per-user custom-permission grid (that complexity can come later if
ever needed). Push back if you want full custom per-user permissions from day one — that's a bigger build.

### Capability matrix (role → what it can do)
| Capability | super_admin | owner | admin | ops/designer | client |
|---|:-:|:-:|:-:|:-:|:-:|
| Manage tenants (agencies) | ✅ | — | — | — | — |
| Manage members / invites | ✅ | ✅ | ✅ | — | — |
| Manage billing | ✅ | ✅ | — | — | — |
| Create/edit clients & brands | ✅ | ✅ | ✅ | scoped | — |
| Briefs / creatives / board | ✅ | ✅ | ✅ | scoped | — |
| Approve (internal) | ✅ | ✅ | ✅ | scoped | — |
| Client portal (view/approve own) | — | — | — | — | ✅ |

Enforced by a new `require_capability(...)` (replacing scattered `require_role` lists) + a scope
check at the data layer (extend the existing tenant filter with a client-scope filter).

## 3. Invitation flow (email OR copyable link)

1. Admin → **Members → Invite** → enters email, picks **role** + **scope** (all / specific clients), optional name.
2. Creates `Invitation(email, tenant_id, role, scopes[], token, expires_at, status=pending)` and returns an
   **accept link** (signed, like `magic_link.py`). Email is sent **if** an email channel is configured;
   otherwise the admin copies the link and sends it manually.
3. Invitee opens link → signs in via Supabase → the pending invite is consumed → `UserAccount` created
   with role + scope, bound to their `auth_subject`. One-time, expiring, revocable, resendable. Audited.

**This ships WITHOUT email first** (copyable link, zero new dependency). Real invite emails need the
`EMAIL` channel — Microsoft Graph `sendMail` from your M365 tenant (previously deferred) — added later,
same seam as WhatsApp.

## 4. Admin panel — screens (frontend, reference-gated → built on Fable)

- **Members**: table (name · email · role · scope · status · last active) + row actions (edit role/scope,
  deactivate, resend/revoke invite).
- **Invite** modal: email · role dropdown · scope multiselect.
- **Client access** view (later): per-client, who has access.

These are UI → need a visual reference (see `docs/DESIGN_REFERENCES.md`; analogs: Linear/Vercel/WorkOS
member settings) and get built on Fable. **Backend ships first, independently.**

## 5. Sequencing (what's unblocked vs gated)

**Buildable NOW (backend, no reference, no email):**
- A. `super_admin` role + gate `POST /tenants` (closes the critical hole).
- B. `require_capability` + the role→capability matrix; add client-**scope** to `UserAccount` (a user↔clients link).
- C. `Invitation` model + create / accept / revoke / resend endpoints returning a **copyable accept link**.

**Gated:**
- Admin panel UI → needs a UI reference + Fable.
- Invite **emails** → needs the M365 Graph `EMAIL` sink (deferrable; copyable link works meanwhile).

## 6. Open decision (need before building)
**Access granularity:** role × scope (§2, recommended) vs full custom per-user permissions. This changes
the data model and every enforcement point — decide first.
