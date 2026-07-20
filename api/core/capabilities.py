"""The role -> capability matrix (IAM increment B, role x scope).

Two independent dimensions (per docs/IAM_DESIGN.md §2):
- Role = what you can DO — a fixed capability set per role (this matrix).
- Scope = which data you SEE — client_scopes on the account / Principal (see api.core.auth).

This is PURELY ADDITIVE. The existing `require_role` guards stay authoritative; this layer
gives the admin UI a machine-readable "what can each role do" and gives `require_capability`
a role-derived alternative that nothing is forced to switch to yet.
"""

from __future__ import annotations

from enum import Enum

from mimik_contracts import ActorRole


class Capability(str, Enum):
    """A discrete thing a principal may do. String-valued so it serializes cleanly on the wire."""

    MANAGE_TENANTS = "manage_tenants"      # create/suspend agencies (platform, cross-tenant)
    MANAGE_MEMBERS = "manage_members"      # invite / provision / deactivate members
    MANAGE_BILLING = "manage_billing"      # subscriptions / billing settings
    MANAGE_CLIENTS = "manage_clients"      # create/edit clients & brands (scope-limited by client_scopes)
    MANAGE_CREATIVES = "manage_creatives"  # briefs / creatives / board (scope-limited)
    APPROVE_INTERNAL = "approve_internal"  # internal (team-side) approval actions (scope-limited)
    CLIENT_PORTAL = "client_portal"        # bounded portal: view/approve/comment on own client


# Reusable groupings mirroring the matrix rows in the design doc.
_SCOPED_WORK = frozenset(
    {Capability.MANAGE_CLIENTS, Capability.MANAGE_CREATIVES, Capability.APPROVE_INTERNAL}
)
_TENANT_ADMIN = _SCOPED_WORK | {Capability.MANAGE_MEMBERS}

# role value -> its capability set. Keyed by ActorRole.value so lookups take the plain role
# string that lives on a Principal.
ROLE_CAPABILITIES: dict[str, frozenset[Capability]] = {
    # Platform operator: everything, across every tenant.
    ActorRole.SUPER_ADMIN.value: frozenset(Capability),
    # Agency owner: everything in the tenant EXCEPT managing other tenants.
    ActorRole.OWNER.value: frozenset(Capability) - {Capability.MANAGE_TENANTS},
    # Senior staff: owner minus billing (and, implicitly, minus manage-tenants).
    ActorRole.ADMIN.value: _TENANT_ADMIN,
    # Staff on assigned clients: scoped work only, no member/billing/tenant management.
    ActorRole.OPS.value: _SCOPED_WORK,
    ActorRole.DESIGNER.value: _SCOPED_WORK,
    # Bootstrap "team" folds into ops-equivalent scoped work.
    ActorRole.TEAM.value: _SCOPED_WORK,
    # External customer: bounded portal only.
    ActorRole.CLIENT.value: frozenset({Capability.CLIENT_PORTAL}),
    # Background jobs: no user-facing capabilities (they run under service auth, not this matrix).
    ActorRole.SYSTEM.value: frozenset(),
}


def capabilities_for(role: str) -> frozenset[Capability]:
    """The capability set for a role value; an unknown role has no capabilities."""
    return ROLE_CAPABILITIES.get(role, frozenset())


def has_capability(role: str, cap: Capability) -> bool:
    """True iff `role` is granted `cap`."""
    return cap in capabilities_for(role)


def capabilities_matrix() -> dict[str, list[str]]:
    """The full role -> [capability values] matrix, JSON-ready for the admin UI."""
    return {
        role: sorted(cap.value for cap in caps) for role, caps in ROLE_CAPABILITIES.items()
    }
