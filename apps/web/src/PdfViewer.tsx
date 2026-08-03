import { useEffect, useRef, useState } from "react";
import * as pdfjs from "pdfjs-dist";
import pdfWorker from "pdfjs-dist/build/pdf.worker.min.mjs?url";

pdfjs.GlobalWorkerOptions.workerSrc = pdfWorker;

type PdfViewerProps = {
  url: string | null;
  page: number;
  searchText?: string;
  onPageChange?: (page: number) => void;
};

export function PdfViewer({
  url,
  page,
  searchText,
  onPageChange,
}: PdfViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const textLayerRef = useRef<HTMLDivElement>(null);
  const [doc, setDoc] = useState<pdfjs.PDFDocumentProxy | null>(null);
  const [numPages, setNumPages] = useState(0);
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "error">(
    "idle",
  );
  const [error, setError] = useState<string | null>(null);
  const [localPage, setLocalPage] = useState(page);

  useEffect(() => {
    setLocalPage(page);
  }, [page]);

  useEffect(() => {
    if (!url) {
      setDoc(null);
      setNumPages(0);
      setStatus("idle");
      return;
    }

    let cancelled = false;
    setStatus("loading");
    setError(null);

    const loadingTask = pdfjs.getDocument(url);
    loadingTask.promise
      .then((pdf) => {
        if (cancelled) {
          pdf.destroy();
          return;
        }
        setDoc(pdf);
        setNumPages(pdf.numPages);
        setStatus("ready");
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setStatus("error");
        setError(err instanceof Error ? err.message : "Falha ao abrir PDF");
      });

    return () => {
      cancelled = true;
      loadingTask.destroy();
    };
  }, [url]);

  useEffect(() => {
    if (!doc || !canvasRef.current || !textLayerRef.current) return;
    const target = Math.min(Math.max(localPage, 1), doc.numPages);
    let cancelled = false;

    (async () => {
      const pdfPage = await doc.getPage(target);
      if (cancelled) return;

      const viewport = pdfPage.getViewport({ scale: 1.15 });
      const canvas = canvasRef.current!;
      const context = canvas.getContext("2d");
      if (!context) return;

      canvas.width = viewport.width;
      canvas.height = viewport.height;

      const textLayer = textLayerRef.current!;
      textLayer.innerHTML = "";
      textLayer.style.width = `${viewport.width}px`;
      textLayer.style.height = `${viewport.height}px`;

      await pdfPage.render({
        canvasContext: context,
        viewport,
      }).promise;
      if (cancelled) return;

      const textContent = await pdfPage.getTextContent();
      if (cancelled) return;

      // Simple text layer for search/highlight (absolute spans)
      const needle = (searchText || "").slice(0, 48).toLowerCase();
      for (const item of textContent.items) {
        if (!("str" in item) || !item.str) continue;
        const tx = pdfjs.Util.transform(viewport.transform, item.transform);
        const fontHeight = Math.hypot(tx[2], tx[3]);
        const span = document.createElement("span");
        span.textContent = item.str;
        span.style.left = `${tx[4]}px`;
        span.style.top = `${tx[5] - fontHeight}px`;
        span.style.fontSize = `${fontHeight}px`;
        span.style.fontFamily = "sans-serif";
        if (needle && item.str.toLowerCase().includes(needle.split(/\s+/)[0]!)) {
          span.className = "pdf-hit";
        }
        textLayer.appendChild(span);
      }
    })().catch((err: unknown) => {
      if (!cancelled) {
        setError(err instanceof Error ? err.message : "Falha ao renderizar");
        setStatus("error");
      }
    });

    return () => {
      cancelled = true;
    };
  }, [doc, localPage, searchText]);

  function go(delta: number) {
    if (!numPages) return;
    const next = Math.min(Math.max(localPage + delta, 1), numPages);
    setLocalPage(next);
    onPageChange?.(next);
  }

  if (!url) {
    return (
      <div className="pdf-empty">
        <p>Nenhum PDF mapeado para esta fila.</p>
        <p className="context">Coloque o arquivo em public/pdfs/ ou atualize o manifesto.</p>
      </div>
    );
  }

  return (
    <div className="pdf-viewer">
      <div className="pdf-toolbar">
        <button type="button" className="btn-ghost" onClick={() => go(-1)} disabled={localPage <= 1}>
          ←
        </button>
        <span>
          p. {localPage} / {numPages || "…"}
        </span>
        <button
          type="button"
          className="btn-ghost"
          onClick={() => go(1)}
          disabled={!numPages || localPage >= numPages}
        >
          →
        </button>
        <button
          type="button"
          className="btn-ghost"
          onClick={() => {
            setLocalPage(page);
            onPageChange?.(page);
          }}
        >
          Ir à página do critério
        </button>
        {status === "loading" && <span className="pill pending">carregando</span>}
        {status === "error" && <span className="pill danger">{error}</span>}
      </div>
      <div className="pdf-scroll">
        <div className="pdf-page">
          <canvas ref={canvasRef} />
          <div ref={textLayerRef} className="pdf-text-layer" />
        </div>
      </div>
    </div>
  );
}
