import { CatalogSource, TestSourceResponse } from "../lib/api";

interface Props {
  source: CatalogSource;
  response: TestSourceResponse | null;
  loading: boolean;
  onClose: () => void;
}

export default function TestResultsDialog({ source, response, loading, onClose }: Props) {
  return (
    <div className="fixed inset-0 z-30 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-3xl max-h-[90vh] overflow-y-auto rounded-lg border border-slate-700 bg-slate-900 p-6 space-y-4">
        <header className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold">Probar fuente: {source.name}</h3>
            <p className="text-xs text-slate-400 mt-1">
              Consulta de prueba con <code className="text-emerald-300">"laptop"</code> (límite 5).
              No se escribe en caché.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200"
            aria-label="Cerrar"
          >
            ✕
          </button>
        </header>

        {loading && <p className="text-slate-400 text-sm">Consultando…</p>}

        {!loading && response && (
          <>
            <div className="flex items-center gap-3 text-xs">
              <span
                className={`px-2 py-0.5 rounded ${
                  response.ok
                    ? "bg-emerald-500/20 text-emerald-300"
                    : "bg-red-500/20 text-red-300"
                }`}
              >
                {response.ok ? "OK" : "Error"}
              </span>
              <span className="text-slate-400">{response.elapsed_ms} ms</span>
              <span className="text-slate-400">
                {response.results.length} resultado(s)
              </span>
            </div>

            {response.error && (
              <div className="rounded border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">
                {response.error}
              </div>
            )}

            {response.results.length > 0 && (
              <ul className="divide-y divide-slate-800 rounded-md border border-slate-800">
                {response.results.map((r, idx) => (
                  <li key={`${r.sku ?? idx}`} className="flex gap-3 p-3">
                    {r.image_url ? (
                      <img
                        src={r.image_url}
                        alt=""
                        className="h-16 w-16 object-cover rounded bg-slate-800"
                      />
                    ) : (
                      <div className="h-16 w-16 rounded bg-slate-800" />
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium truncate">{r.product_name}</div>
                      <div className="text-xs text-slate-400">
                        {r.currency} {r.unit_price} · entrega ~{r.lead_time_days}d · stock {r.available_stock}
                      </div>
                      {r.url && (
                        <a
                          href={r.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-emerald-400 hover:underline truncate block"
                        >
                          {r.url}
                        </a>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </div>
    </div>
  );
}
