"""Bootstrap the FIRST tenant + a super-admin account into an empty database.

The invite/provision flows all require an existing owner/super_admin, so a fresh
deployment needs this one-time bootstrap. It is idempotent: an existing tenant (by
slug) or account (by auth_subject) is reused, never duplicated.

Prereq: the operator has already created the Supabase auth user (email + password)
in the Supabase dashboard and copied that user's UID (the `auth_subject`).

Run on the VPS, inside the api container, with DATABASE_URL already in the env:

    docker exec -i mimiksuite-api-1 \
      env BOOTSTRAP_EMAIL="you@example.com" \
          BOOTSTRAP_AUTH_SUBJECT="<supabase-user-uid>" \
          BOOTSTRAP_TENANT_NAME="Mimik Creations" \
          BOOTSTRAP_TENANT_SLUG="mimik" \
          BOOTSTRAP_ROLE="owner" \
      python - < scripts/bootstrap_superadmin.py

Role note: if BOOTSTRAP_EMAIL is on SUPERADMIN_EMAILS, the account is elevated to
super_admin at request time regardless of the stored role — so "owner" here still
logs in with full platform (cross-tenant) powers.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys

from api.db import repo
from api.db.session import get_engine, get_sessionmaker


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "tenant"


async def main() -> None:
    email = os.environ.get("BOOTSTRAP_EMAIL", "").strip()
    auth_subject = os.environ.get("BOOTSTRAP_AUTH_SUBJECT", "").strip()
    tenant_name = os.environ.get("BOOTSTRAP_TENANT_NAME", "Mimik Creations").strip()
    tenant_slug = _slugify(os.environ.get("BOOTSTRAP_TENANT_SLUG", tenant_name))
    role = os.environ.get("BOOTSTRAP_ROLE", "owner").strip()

    if not email or not auth_subject:
        sys.exit("BOOTSTRAP_EMAIL and BOOTSTRAP_AUTH_SUBJECT are required.")

    maker = get_sessionmaker()
    async with maker() as session:
        # Tenant: reuse by slug, else create.
        tenant = await repo.get_tenant_by_slug(session, slug=tenant_slug)
        if tenant is None:
            tenant = await repo.create_tenant(session, name=tenant_name, slug=tenant_slug)
            print(f"[tenant] created id={tenant.id} name={tenant_name!r} slug={tenant_slug!r}")
        else:
            print(f"[tenant] reused  id={tenant.id} slug={tenant_slug!r}")

        # Account: reuse by auth_subject (unique), else create.
        existing = await repo.get_user_account_by_subject(session, auth_subject=auth_subject)
        if existing is not None:
            print(
                f"[account] already exists id={existing.id} email={existing.email!r} "
                f"role={existing.role!r} active={existing.active} — no change."
            )
        else:
            acct = await repo.create_user_account(
                session,
                tenant_id=tenant.id,
                auth_subject=auth_subject,
                email=email,
                role=role,
                client_scopes=[],
                name=None,
                active=True,
            )
            await session.commit()
            print(
                f"[account] created  id={acct.id} email={email!r} role={role!r} "
                f"tenant_id={tenant.id}"
            )

    await get_engine().dispose()
    print("bootstrap done. Log in at https://suite.mimikcreations.com/login")


if __name__ == "__main__":
    asyncio.run(main())
