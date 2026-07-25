"use client";

import Link from "next/link";
import { useState, useTransition, type JSX } from "react";
import { useRouter } from "next/navigation";
import { removeClientAction } from "@/app/crud-actions";
import type { SidebarProject } from "@/lib/view-models";
import { ShapeIcon } from "./icons";

interface ClientsListViewProps {
  clients: SidebarProject[];
}

const CLIENT_CRUD_CSS = `
  .client-gallery__item { position: relative; }
  .client-gallery__remove {
    position: absolute; top: 10px; right: 10px; z-index: 1;
    color: var(--danger, #b42318); background: var(--surface);
  }
  .client-gallery__error { margin-bottom: var(--sp-3); color: var(--danger, #b42318); font-size: 12px; }
`;

export function ClientsListView({ clients }: ClientsListViewProps): JSX.Element {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");

  function remove(client: SidebarProject): void {
    if (!window.confirm(`Remove “${client.name}”? It will be hidden, not destroyed.`)) return;
    setBusyId(client.id);
    setError("");
    startTransition(async () => {
      const result = await removeClientAction(client.id);
      setBusyId(null);
      if (result.ok) {
        router.refresh();
      } else {
        setError(result.error ?? "Could not remove this client.");
      }
    });
  }

  return (
    <>
      <style>{CLIENT_CRUD_CSS}</style>
      {error !== "" && (
        <p className="client-gallery__error" role="alert">
          {error}
        </p>
      )}
      <ul className="gallery" aria-label="Clients">
        {clients.map((client) => (
          <li key={client.id} className="client-gallery__item">
            <Link
              href={`/clients/${encodeURIComponent(client.id)}/edit`}
              className="gallery-card gallery-card--client"
              aria-label={`Edit ${client.name}`}
            >
              <span className={`project-row__shape shape--${client.tone}`} aria-hidden="true">
                <ShapeIcon shape={client.shape} />
              </span>
              <span className="gallery-card__meta">
                <span className="gallery-card__title">{client.name}</span>
                <span className="gallery-card__version">
                  {client.count === 1 ? "1 open job" : `${client.count} open jobs`}
                </span>
              </span>
            </Link>
            <button
              type="button"
              className="btn btn--ghost btn--sm client-gallery__remove"
              disabled={pending && busyId === client.id}
              onClick={(): void => remove(client)}
            >
              {pending && busyId === client.id ? "Removing…" : "Remove"}
            </button>
          </li>
        ))}
      </ul>
    </>
  );
}
