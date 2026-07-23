"use client";

import { useState, useRef, useEffect, type JSX } from "react";
import Link from "next/link";
import { ChevronDownIcon } from "./icons";
import type { Client } from "@/lib/view-models";

export function ClientSwitcher({ activeClient, clients }: { activeClient: Client; clients: { id: string; name: string }[] }): JSX.Element {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button
        type="button"
        className="client-chip"
        aria-label="Switch active client"
        onClick={() => setOpen(!open)}
      >
        <span className="client-chip__dot" aria-hidden="true" />
        <span>
          {activeClient.name} · {activeClient.vertical}
        </span>
        <span className="client-chip__caret" aria-hidden="true">
          <ChevronDownIcon size={12} />
        </span>
      </button>

      {open && (
        <div
          style={{
            position: "absolute",
            top: "calc(100% + 4px)",
            left: 0,
            background: "var(--surface)",
            border: "1px solid var(--card-border)",
            borderRadius: "var(--r-sm)",
            boxShadow: "var(--shadow-pop)",
            minWidth: "200px",
            zIndex: 100,
            display: "flex",
            flexDirection: "column",
            padding: "4px",
          }}
        >
          {clients.map((client) => {
            const isActive = client.id === activeClient.id;
            return (
              <Link
                key={client.id}
                href={`/clients/${encodeURIComponent(client.id)}/edit`}
                onClick={() => setOpen(false)}
                style={{
                  padding: "8px 12px",
                  borderRadius: "var(--r-sm)",
                  fontSize: "13px",
                  fontWeight: isActive ? 600 : 500,
                  color: isActive ? "var(--ink)" : "var(--ink-2)",
                  background: isActive ? "var(--surface-2)" : "transparent",
                  textDecoration: "none",
                  display: "block",
                }}
              >
                {client.name}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
