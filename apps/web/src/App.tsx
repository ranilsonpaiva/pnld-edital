import { useEffect, useMemo, useState } from "react";
import { RequireAuth, useAuth } from "./auth";
import type {
  CriterionItem,
  ManifestEntry,
  QueuePayload,
  ReviewAction,
  ReviewEvent,
} from "./types";

const STORAGE_KEY = "pnld-hitl-reviews-v1";

function loadReviews(): ReviewEvent[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as ReviewEvent[]) : [];
  } catch {
    return [];
  }
}

function saveReviews(events: ReviewEvent[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(events));
}

function statusPill(action: ReviewAction | undefined) {
  if (!action) return <span className="pill pending">pendente</span>;
  if (action === "approve") return <span className="pill ok">aprovado</span>;
  if (action === "edit") return <span className="pill warn">editado</span>;
  if (action === "reject") return <span className="pill danger">rejeitado</span>;
  return <span className="pill">pulado</span>;
}

export default function App() {
  const { enabled: authEnabled, user, signOut } = useAuth();
  const [manifest, setManifest] = useState<ManifestEntry[]>([]);
  const [queueId, setQueueId] = useState<string>("");
  const [queue, setQueue] = useState<QueuePayload | null>(null);
  const [index, setIndex] = useState(0);
  const [draft, setDraft] = useState("");
  const [note, setNote] = useState("");
  const [reviews, setReviews] = useState<ReviewEvent[]>(() => loadReviews());
  const [filter, setFilter] = useState<"pending" | "all">("pending");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/data/manifest.json")
      .then((r) => r.json())
      .then((data: ManifestEntry[]) => {
        setManifest(data);
        if (data[0]) setQueueId(data[0].id);
      })
      .catch(() => setError("Não foi possível carregar o manifesto."));
  }, []);

  useEffect(() => {
    if (!queueId || manifest.length === 0) return;
    const entry = manifest.find((m) => m.id === queueId);
    if (!entry) return;
    setError(null);
    fetch(`/data/${entry.file}`)
      .then((r) => r.json())
      .then((data: QueuePayload) => {
        setQueue(data);
        setIndex(0);
      })
      .catch(() => setError("Não foi possível carregar a fila."));
  }, [queueId, manifest]);

  const latestByCode = useMemo(() => {
    const map = new Map<string, ReviewEvent>();
    for (const event of reviews) {
      if (event.queueId !== queueId) continue;
      map.set(event.code, event);
    }
    return map;
  }, [reviews, queueId]);

  const visibleItems = useMemo(() => {
    if (!queue) return [] as CriterionItem[];
    if (filter === "all") return queue.items;
    return queue.items.filter((item) => !latestByCode.has(item.code));
  }, [queue, filter, latestByCode]);

  useEffect(() => {
    if (visibleItems.length === 0) {
      setDraft("");
      return;
    }
    const safeIndex = Math.min(index, visibleItems.length - 1);
    if (safeIndex !== index) setIndex(safeIndex);
    const current = visibleItems[safeIndex];
    const existing = latestByCode.get(current.code);
    setDraft(existing?.after || current.statement);
    setNote(existing?.note || "");
  }, [visibleItems, index, latestByCode]);

  const current = visibleItems[index] ?? null;
  const reviewedCount = queue
    ? queue.items.filter((item) => latestByCode.has(item.code)).length
    : 0;
  const approved = [...latestByCode.values()].filter((e) => e.action === "approve").length;
  const edited = [...latestByCode.values()].filter((e) => e.action === "edit").length;
  const rejected = [...latestByCode.values()].filter((e) => e.action === "reject").length;

  function commit(action: ReviewAction) {
    if (!queue || !current) return;
    const after =
      action === "reject"
        ? current.statement
        : action === "approve"
          ? current.statement
          : draft.trim() || current.statement;

    if (action === "edit" && after === current.statement && !note.trim()) {
      // treat unchanged edit as approve unless note provided
    }

    const event: ReviewEvent = {
      id: crypto.randomUUID(),
      queueId: queue.id,
      code: current.code,
      action:
        action === "edit" && after === current.statement ? "approve" : action,
      before: current.statement,
      after,
      criterion_type: current.criterion_type,
      section_code: current.section_code,
      page_start: current.page_start,
      note: note.trim(),
      reviewedAt: new Date().toISOString(),
    };

    const next = [
      ...reviews.filter(
        (r) => !(r.queueId === event.queueId && r.code === event.code),
      ),
      event,
    ];
    setReviews(next);
    saveReviews(next);

    if (filter === "pending") {
      // item disappears; keep index pointing to next pending
      setNote("");
    } else if (index < visibleItems.length - 1) {
      setIndex(index + 1);
      setNote("");
    }
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "TEXTAREA" || tag === "INPUT" || tag === "SELECT") {
        if (e.key === "Escape") (e.target as HTMLElement).blur();
        return;
      }
      if (e.key === "a" || e.key === "A") commit("approve");
      if (e.key === "e" || e.key === "E") {
        const area = document.getElementById("draft") as HTMLTextAreaElement | null;
        area?.focus();
      }
      if (e.key === "r" || e.key === "R") commit("reject");
      if (e.key === "j" || e.key === "ArrowDown") {
        setIndex((i) => Math.min(i + 1, Math.max(visibleItems.length - 1, 0)));
      }
      if (e.key === "k" || e.key === "ArrowUp") {
        setIndex((i) => Math.max(i - 1, 0));
      }
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") commit("edit");
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  function exportReviews() {
    const blob = new Blob([JSON.stringify(reviews, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `pnld-hitl-reviews-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function clearQueueReviews() {
    if (!queue) return;
    if (!confirm(`Limpar revisões desta fila (${queue.label})?`)) return;
    const next = reviews.filter((r) => r.queueId !== queue.id);
    setReviews(next);
    saveReviews(next);
  }

  return (
    <RequireAuth>
    <div className="app">
      <header className="topbar">
        <div>
          <h1 className="brand">PNLD HITL</h1>
          <p className="sub">
            Validação supervisionada de critérios · Anexo 01 §§3–4
          </p>
        </div>
        <div className="controls">
          {!authEnabled ? (
            <span className="pill pending">acesso aberto · auth prevista</span>
          ) : user ? (
            <span className="pill ok">
              {user.name}
              <button
                type="button"
                className="btn-ghost"
                style={{ marginLeft: 8, padding: "2px 8px" }}
                onClick={signOut}
              >
                Sair
              </button>
            </span>
          ) : null}
          <select
            value={queueId}
            onChange={(e) => setQueueId(e.target.value)}
            aria-label="Fila"
          >
            {manifest.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label} ({m.count})
              </option>
            ))}
          </select>
          <select
            value={filter}
            onChange={(e) => {
              setFilter(e.target.value as "pending" | "all");
              setIndex(0);
            }}
            aria-label="Filtro"
          >
            <option value="pending">Só pendentes</option>
            <option value="all">Todos</option>
          </select>
          <button type="button" className="btn-ghost" onClick={exportReviews}>
            Exportar JSON
          </button>
          <button type="button" className="btn-ghost" onClick={clearQueueReviews}>
            Limpar fila
          </button>
        </div>
      </header>

      {error && <p className="empty">{error}</p>}

      <div className="stats">
        <div className="stat">
          <strong>
            {reviewedCount}/{queue?.count ?? 0}
          </strong>
          <span>revisados</span>
        </div>
        <div className="stat">
          <strong>{approved}</strong>
          <span>aprovados</span>
        </div>
        <div className="stat">
          <strong>{edited}</strong>
          <span>editados</span>
        </div>
        <div className="stat">
          <strong>{rejected}</strong>
          <span>rejeitados</span>
        </div>
      </div>

      <div className="layout">
        <aside className="panel">
          <div className="panel-header">
            <h2>Fila</h2>
            <span className="pill">{visibleItems.length}</span>
          </div>
          <div className="queue">
            {visibleItems.map((item, i) => {
              const review = latestByCode.get(item.code);
              return (
                <button
                  key={item.code}
                  type="button"
                  className={`queue-item${i === index ? " active" : ""}`}
                  onClick={() => setIndex(i)}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      gap: 8,
                    }}
                  >
                    <span className="code">{item.code}</span>
                    {statusPill(review?.action)}
                  </div>
                  <span className="snip">{item.statement}</span>
                </button>
              );
            })}
            {visibleItems.length === 0 && (
              <p className="empty">Nenhum item neste filtro.</p>
            )}
          </div>
        </aside>

        <section className="panel">
          {!current ? (
            <p className="empty">Fila concluída ou vazia.</p>
          ) : (
            <>
              <div className="panel-header">
                <h2>
                  {current.code}
                  {current.parent_code ? ` · pai ${current.parent_code}` : ""}
                </h2>
                {statusPill(latestByCode.get(current.code)?.action)}
              </div>
              <div className="main-body">
                <div className="meta-row">
                  <span className="pill">{current.kind}</span>
                  <span className="pill">{current.criterion_type}</span>
                  <span className="pill">
                    §{current.section_code} · p.{current.page_start}
                  </span>
                  <span className="pill">
                    {current.mandatory_guess ? "obrigatório?" : "facultativo?"}
                  </span>
                  {current.applies_to.map((tag) => (
                    <span className="pill" key={tag}>
                      {tag}
                    </span>
                  ))}
                </div>

                <p className="context">{current.section_title}</p>
                <p className="statement">{current.statement}</p>

                <div className="editor">
                  <label htmlFor="draft">Texto corrigido (para Editar)</label>
                  <textarea
                    id="draft"
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                  />
                  <label htmlFor="note">Nota do revisor (opcional)</label>
                  <textarea
                    id="note"
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    style={{ minHeight: 72 }}
                  />
                </div>
              </div>
              <div className="actions">
                <button
                  type="button"
                  className="btn btn-ok"
                  onClick={() => commit("approve")}
                >
                  Aprovar (A)
                </button>
                <button
                  type="button"
                  className="btn btn-warn"
                  onClick={() => commit("edit")}
                >
                  Salvar edição (⌘↵)
                </button>
                <button
                  type="button"
                  className="btn btn-danger"
                  onClick={() => commit("reject")}
                >
                  Rejeitar (R)
                </button>
                <button
                  type="button"
                  className="btn-ghost"
                  onClick={() =>
                    setIndex((i) =>
                      Math.min(i + 1, Math.max(visibleItems.length - 1, 0)),
                    )
                  }
                >
                  Pular (J)
                </button>
                <span className="hint">
                  A aprovar · E focar edição · R rejeitar · J/K navegar
                </span>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
    </RequireAuth>
  );
}
