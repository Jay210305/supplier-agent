import { FormEvent, useMemo, useState } from "react";
import {
  AdapterInfo,
  CatalogSource,
  CatalogSourceInput,
  CatalogSourceKind,
} from "../lib/api";

interface Props {
  source: CatalogSource | null;
  adapters: AdapterInfo[];
  onClose: () => void;
  onSave: (input: CatalogSourceInput, id?: number) => Promise<void>;
}

interface FormState {
  name: string;
  kind: CatalogSourceKind;
  adapter_key: string;
  endpoint: string;
  is_enabled: boolean;
  country: string;
  currency: string;
  reliability_rating: string;
  rate_limit_per_min: string;
  timeout_seconds: string;
  authJson: string;
  configJson: string;
  notes: string;
}

function initialState(source: CatalogSource | null, adapters: AdapterInfo[]): FormState {
  const defaultAdapter = adapters[0]?.key ?? "";
  if (!source) {
    return {
      name: "",
      kind: "website",
      adapter_key: defaultAdapter,
      endpoint: "",
      is_enabled: true,
      country: "PE",
      currency: "PEN",
      reliability_rating: "5.00",
      rate_limit_per_min: "20",
      timeout_seconds: "15",
      authJson: "",
      configJson: "",
      notes: "",
    };
  }
  return {
    name: source.name,
    kind: source.kind,
    adapter_key: source.adapter_key,
    endpoint: source.endpoint,
    is_enabled: source.is_enabled,
    country: source.country ?? "",
    currency: source.currency,
    reliability_rating: String(source.reliability_rating),
    rate_limit_per_min: String(source.rate_limit_per_min),
    timeout_seconds: String(source.timeout_seconds),
    authJson: source.auth ? JSON.stringify(source.auth, null, 2) : "",
    configJson: source.config ? JSON.stringify(source.config, null, 2) : "",
    notes: source.notes ?? "",
  };
}

function parseJsonField(raw: string): Record<string, unknown> | null | undefined {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  const parsed = JSON.parse(trimmed);
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    throw new Error("Debe ser un objeto JSON");
  }
  return parsed as Record<string, unknown>;
}

export default function SourceFormDialog({ source, adapters, onClose, onSave }: Props) {
  const [state, setState] = useState<FormState>(() => initialState(source, adapters));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedAdapter = useMemo(
    () => adapters.find((a) => a.key === state.adapter_key),
    [adapters, state.adapter_key],
  );

  const update = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setState((prev) => ({ ...prev, [key]: value }));

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    let auth: Record<string, unknown> | null | undefined;
    let config: Record<string, unknown> | null | undefined;
    try {
      auth = parseJsonField(state.authJson);
      config = parseJsonField(state.configJson);
    } catch (err) {
      setError(`JSON inválido: ${err instanceof Error ? err.message : err}`);
      return;
    }

    const input: CatalogSourceInput = {
      name: state.name.trim(),
      kind: state.kind,
      adapter_key: state.adapter_key,
      endpoint: state.endpoint.trim(),
      is_enabled: state.is_enabled,
      country: state.country.trim() ? state.country.trim().toUpperCase() : null,
      currency: state.currency.trim().toUpperCase() || "PEN",
      reliability_rating: Number(state.reliability_rating),
      rate_limit_per_min: Number(state.rate_limit_per_min),
      timeout_seconds: Number(state.timeout_seconds),
      auth,
      config,
      notes: state.notes.trim() || null,
    };

    setSubmitting(true);
    try {
      await onSave(input, source?.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al guardar");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-30 flex items-center justify-center bg-black/60 p-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-lg border border-slate-700 bg-slate-900 p-6 space-y-4"
      >
        <header className="flex items-center justify-between">
          <h3 className="text-lg font-semibold">
            {source ? `Editar: ${source.name}` : "Nueva fuente externa"}
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200"
            aria-label="Cerrar"
          >
            ✕
          </button>
        </header>

        {error && (
          <div className="rounded border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="Nombre">
            <input
              required
              value={state.name}
              onChange={(e) => update("name", e.target.value)}
              className={inputCls}
            />
          </Field>
          <Field label="Tipo">
            <select
              value={state.kind}
              onChange={(e) => update("kind", e.target.value as CatalogSourceKind)}
              className={inputCls}
            >
              <option value="website">website</option>
              <option value="email">email</option>
            </select>
          </Field>
          <Field label="Adapter">
            <select
              value={state.adapter_key}
              onChange={(e) => update("adapter_key", e.target.value)}
              className={inputCls}
            >
              {adapters.map((a) => (
                <option key={a.key} value={a.key}>
                  {a.key} — {a.kind}
                </option>
              ))}
            </select>
            {selectedAdapter && (
              <p className="text-xs text-slate-400 mt-1">
                {selectedAdapter.description}
                {selectedAdapter.requires_auth && (
                  <span className="block text-amber-400 mt-0.5">
                    Requiere campos en JSON Auth:{" "}
                    {selectedAdapter.auth_fields.join(", ")}
                  </span>
                )}
                {selectedAdapter.config_fields.length > 0 && (
                  <span className="block text-slate-500 mt-0.5">
                    Config sugerida: {selectedAdapter.config_fields.join(", ")}
                  </span>
                )}
              </p>
            )}
          </Field>
          <Field label={state.kind === "email" ? "Email destino" : "URL base"}>
            <input
              required
              value={state.endpoint}
              onChange={(e) => update("endpoint", e.target.value)}
              className={inputCls}
              placeholder={
                state.kind === "email"
                  ? "cotizaciones@proveedor.pe"
                  : "https://api.example.com"
              }
            />
          </Field>
          <Field label="País (ISO-2)">
            <input
              value={state.country}
              maxLength={2}
              onChange={(e) => update("country", e.target.value)}
              className={inputCls}
            />
          </Field>
          <Field label="Moneda (ISO-3)">
            <input
              value={state.currency}
              maxLength={3}
              onChange={(e) => update("currency", e.target.value)}
              className={inputCls}
            />
          </Field>
          <Field label="Confiabilidad (0–10)">
            <input
              type="number"
              step="0.01"
              min={0}
              max={10}
              value={state.reliability_rating}
              onChange={(e) => update("reliability_rating", e.target.value)}
              className={inputCls}
            />
          </Field>
          <Field label="Rate-limit / min">
            <input
              type="number"
              min={1}
              value={state.rate_limit_per_min}
              onChange={(e) => update("rate_limit_per_min", e.target.value)}
              className={inputCls}
            />
          </Field>
          <Field label="Timeout (s)">
            <input
              type="number"
              min={1}
              max={120}
              value={state.timeout_seconds}
              onChange={(e) => update("timeout_seconds", e.target.value)}
              className={inputCls}
            />
          </Field>
          <Field label="Activa">
            <label className="inline-flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={state.is_enabled}
                onChange={(e) => update("is_enabled", e.target.checked)}
              />
              <span>El agente la consulta al ejecutar /procurement/parse</span>
            </label>
          </Field>
        </div>

        <Field label="Auth (JSON)">
          <textarea
            rows={3}
            value={state.authJson}
            onChange={(e) => update("authJson", e.target.value)}
            className={`${inputCls} font-mono text-xs`}
            placeholder='{"oauth_token": "..."}'
          />
        </Field>
        <Field label="Config (JSON)">
          <textarea
            rows={5}
            value={state.configJson}
            onChange={(e) => update("configJson", e.target.value)}
            className={`${inputCls} font-mono text-xs`}
            placeholder='{"site_id": "MPE"}'
          />
        </Field>
        <Field label="Notas">
          <textarea
            rows={2}
            value={state.notes}
            onChange={(e) => update("notes", e.target.value)}
            className={inputCls}
          />
        </Field>

        <footer className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-md text-slate-300 hover:bg-slate-800"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="px-4 py-2 text-sm rounded-md bg-emerald-500 text-slate-950 font-medium hover:bg-emerald-400 disabled:opacity-50"
          >
            {submitting ? "Guardando…" : "Guardar"}
          </button>
        </footer>
      </form>
    </div>
  );
}

const inputCls =
  "w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-xs uppercase tracking-wide text-slate-400 mb-1">
        {label}
      </span>
      {children}
    </label>
  );
}
