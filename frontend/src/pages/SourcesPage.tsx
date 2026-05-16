import { useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  AdapterInfo,
  CatalogSource,
  CatalogSourceInput,
  CatalogSourceKind,
  TestSourceResponse,
} from "../lib/api";
import SourceFormDialog from "../components/SourceFormDialog";
import TestResultsDialog from "../components/TestResultsDialog";

export default function SourcesPage() {
  const [sources, setSources] = useState<CatalogSource[]>([]);
  const [adapters, setAdapters] = useState<AdapterInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<CatalogSource | null>(null);
  const [creating, setCreating] = useState(false);
  const [testTarget, setTestTarget] = useState<CatalogSource | null>(null);
  const [testResult, setTestResult] = useState<TestSourceResponse | null>(null);
  const [testing, setTesting] = useState(false);

  const adapterByKey = useMemo(
    () => Object.fromEntries(adapters.map((a) => [a.key, a])),
    [adapters],
  );

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, a] = await Promise.all([api.listSources(), api.listAdapters()]);
      setSources(s);
      setAdapters(a);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error desconocido");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleToggle = async (s: CatalogSource) => {
    try {
      await api.updateSource(s.id, { is_enabled: !s.is_enabled });
      await refresh();
    } catch (e) {
      alert(e instanceof Error ? e.message : "No se pudo actualizar");
    }
  };

  const handleDelete = async (s: CatalogSource) => {
    if (!confirm(`¿Eliminar la fuente "${s.name}"? Esta acción no se puede deshacer.`)) return;
    try {
      await api.deleteSource(s.id);
      await refresh();
    } catch (e) {
      alert(e instanceof Error ? e.message : "No se pudo eliminar");
    }
  };

  const handleSave = async (input: CatalogSourceInput, id?: number) => {
    if (id) await api.updateSource(id, input);
    else await api.createSource(input);
    setCreating(false);
    setEditing(null);
    await refresh();
  };

  const handleTest = async (s: CatalogSource) => {
    setTestTarget(s);
    setTestResult(null);
    setTesting(true);
    try {
      const result = await api.testSource(s.id, "laptop", 5);
      setTestResult(result);
    } catch (e) {
      setTestResult({
        source_id: s.id,
        source_name: s.name,
        adapter_key: s.adapter_key,
        query: "laptop",
        elapsed_ms: 0,
        ok: false,
        error: e instanceof Error ? e.message : "Error desconocido",
        results: [],
      });
    } finally {
      setTesting(false);
    }
  };

  return (
    <section className="space-y-6">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Fuentes externas</h2>
          <p className="text-slate-400 text-sm mt-1">
            Catálogos web y direcciones de cotización que el agente puede consultar al
            recibir un pedido de procura.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setCreating(true)}
          className="rounded-md bg-emerald-500 px-4 py-2 text-sm font-medium text-slate-950 hover:bg-emerald-400"
        >
          + Nueva fuente
        </button>
      </div>

      {error && (
        <div className="rounded-md border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border border-slate-800 bg-slate-900">
        <table className="min-w-full text-sm">
          <thead className="text-slate-400 text-xs uppercase tracking-wide">
            <tr>
              <th className="px-4 py-3 text-left">Nombre</th>
              <th className="px-4 py-3 text-left">Tipo</th>
              <th className="px-4 py-3 text-left">Adapter</th>
              <th className="px-4 py-3 text-left">Endpoint</th>
              <th className="px-4 py-3 text-left">Conf.</th>
              <th className="px-4 py-3 text-left">Estado</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {loading && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-slate-400 text-center">
                  Cargando…
                </td>
              </tr>
            )}
            {!loading && sources.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-slate-400 text-center">
                  Aún no hay fuentes configuradas. Ejecuta{" "}
                  <code className="text-emerald-400">
                    docker exec fastapi python -m db.seed_catalog_sources
                  </code>{" "}
                  o crea una nueva.
                </td>
              </tr>
            )}
            {sources.map((s) => (
              <tr key={s.id} className="hover:bg-slate-800/40">
                <td className="px-4 py-3 font-medium">
                  {s.name}
                  {s.notes && (
                    <div className="text-xs text-slate-500 mt-0.5 max-w-md">
                      {s.notes}
                    </div>
                  )}
                </td>
                <td className="px-4 py-3">
                  <KindBadge kind={s.kind} />
                </td>
                <td className="px-4 py-3">
                  <code className="text-xs text-emerald-300">{s.adapter_key}</code>
                  {adapterByKey[s.adapter_key]?.requires_auth && (
                    <span
                      className="ml-2 text-xs text-amber-400"
                      title="Requiere credenciales"
                    >
                      🔑
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-slate-300 max-w-xs truncate">
                  {s.endpoint}
                </td>
                <td className="px-4 py-3 text-slate-400 text-xs">
                  {s.country ?? "—"} · {s.currency} · ⭐ {s.reliability_rating}
                </td>
                <td className="px-4 py-3">
                  <button
                    type="button"
                    onClick={() => handleToggle(s)}
                    className={`text-xs px-2 py-1 rounded ${
                      s.is_enabled
                        ? "bg-emerald-500/20 text-emerald-300"
                        : "bg-slate-700 text-slate-300"
                    }`}
                  >
                    {s.is_enabled ? "Activa" : "Inactiva"}
                  </button>
                </td>
                <td className="px-4 py-3 text-right whitespace-nowrap">
                  <button
                    type="button"
                    onClick={() => handleTest(s)}
                    className="text-xs text-slate-300 hover:text-emerald-300 px-2 py-1"
                  >
                    Probar
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditing(s)}
                    className="text-xs text-slate-300 hover:text-emerald-300 px-2 py-1"
                  >
                    Editar
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(s)}
                    className="text-xs text-red-400 hover:text-red-300 px-2 py-1"
                  >
                    Eliminar
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {(creating || editing) && (
        <SourceFormDialog
          source={editing}
          adapters={adapters}
          onClose={() => {
            setCreating(false);
            setEditing(null);
          }}
          onSave={handleSave}
        />
      )}

      {testTarget && (
        <TestResultsDialog
          source={testTarget}
          response={testResult}
          loading={testing}
          onClose={() => {
            setTestTarget(null);
            setTestResult(null);
          }}
        />
      )}
    </section>
  );
}

function KindBadge({ kind }: { kind: CatalogSourceKind }) {
  const cls =
    kind === "website"
      ? "bg-sky-500/20 text-sky-300"
      : "bg-violet-500/20 text-violet-300";
  return <span className={`text-xs px-2 py-0.5 rounded ${cls}`}>{kind}</span>;
}
