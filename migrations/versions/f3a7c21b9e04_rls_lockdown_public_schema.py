"""Enable RLS on every app table in `public` and revoke the PostgREST role grants.

In production Postgres IS the Supabase project (docker-compose.prod.yml: "Postgres is
EXTERNAL (Supabase)"), so every table Alembic creates lands in a schema Supabase auto-
exposes over PostgREST. With RLS off, the project URL + anon key reads and writes every
tenant's rows directly, bypassing the API entirely — locked constraint #2 (tenant authZ
at the DATA layer) is void no matter how correct the route filters are.

Nothing in this product talks to PostgREST: `web/` has no @supabase/supabase-js dependency
and reaches the API over NEXT_PUBLIC_API_URL; Supabase is used ONLY to issue and verify
JWTs (api/core/supabase_auth.py). So RLS with ZERO policies is the correct posture — a
default deny for `anon`/`authenticated`.

The API keeps working because it connects as the role that OWNS these tables, and an owner
bypasses RLS. That bypass is deliberate and load-bearing: we do NOT use FORCE ROW LEVEL
SECURITY, which would strip it and take the backend down with it.

Belt-and-braces: Supabase grants `anon`/`authenticated` broad table privileges in `public`
by default. Revoking them means a future accidental permissive policy still exposes nothing.

Both statements iterate the live catalog rather than a hardcoded list, so this also covers
`alembic_version` and any table created outside these migrations (dashboard, ad-hoc SQL) —
which is likely what tripped the linter in the first place. Tables not owned by the current
role, and extension-owned tables, are skipped: we cannot ALTER them and they are not ours.

Revision ID: f3a7c21b9e04
Revises: d41f83a2c906
Create Date: 2026-07-29
"""

from typing import Sequence, Union

from alembic import op


revision: str = "f3a7c21b9e04"
down_revision: Union[str, None] = "d41f83a2c906"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tables we own in `public`, excluding anything owned by an installed extension
# (pg_depend deptype 'e') — those belong to the extension and ALTER would fail.
_OWNED_PUBLIC_TABLES = """
    SELECT c.oid, c.relname
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relkind = 'r'
      AND pg_get_userbyid(c.relowner) = current_user
      AND NOT EXISTS (
          SELECT 1 FROM pg_depend d
          WHERE d.classid = 'pg_class'::regclass
            AND d.objid = c.oid
            AND d.deptype = 'e'
      )
"""

# The PostgREST roles. They do not exist on the local :5434 dev Postgres, so every
# GRANT/REVOKE is guarded on pg_roles — the migration must run clean in both places.
_POSTGREST_ROLES = ("anon", "authenticated")


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        DECLARE t record;
        BEGIN
            FOR t IN {_OWNED_PUBLIC_TABLES} LOOP
                EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t.relname);
            END LOOP;
        END $$;
        """
    )

    for role in _POSTGREST_ROLES:
        op.execute(
            f"""
            DO $$
            DECLARE t record;
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                    RETURN;
                END IF;
                FOR t IN {_OWNED_PUBLIC_TABLES} LOOP
                    EXECUTE format(
                        'REVOKE ALL PRIVILEGES ON public.%I FROM {role}', t.relname
                    );
                END LOOP;
                REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM {role};
                REVOKE USAGE ON SCHEMA public FROM {role};
            END $$;
            """
        )


def downgrade() -> None:
    """Restore the pre-migration posture (Supabase's permissive defaults).

    Non-destructive and exactly reversible, but note what reversing MEANS here: it puts
    every tenant's rows back on the public internet behind a non-secret anon key. Only
    run this to unblock a rollback, never as a fix.
    """
    for role in _POSTGREST_ROLES:
        op.execute(
            f"""
            DO $$
            DECLARE t record;
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                    RETURN;
                END IF;
                GRANT USAGE ON SCHEMA public TO {role};
                GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO {role};
                FOR t IN {_OWNED_PUBLIC_TABLES} LOOP
                    EXECUTE format(
                        'GRANT ALL PRIVILEGES ON public.%I TO {role}', t.relname
                    );
                END LOOP;
            END $$;
            """
        )

    op.execute(
        f"""
        DO $$
        DECLARE t record;
        BEGIN
            FOR t IN {_OWNED_PUBLIC_TABLES} LOOP
                EXECUTE format('ALTER TABLE public.%I DISABLE ROW LEVEL SECURITY', t.relname);
            END LOOP;
        END $$;
        """
    )
