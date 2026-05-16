const API_BASE = "/api";

export type CatalogSourceKind = "website" | "email";

export interface AdapterInfo {
  key: string;
  kind: CatalogSourceKind;
  description: string;
  requires_auth: boolean;
  auth_fields: string[];
  config_fields: string[];
}

export interface CatalogSource {
  id: number;
  name: string;
  kind: CatalogSourceKind;
  adapter_key: string;
  endpoint: string;
  is_enabled: boolean;
  country: string | null;
  currency: string;
  reliability_rating: string;
  rate_limit_per_min: number;
  timeout_seconds: number;
  auth: Record<string, unknown> | null;
  config: Record<string, unknown> | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface CatalogSourceInput {
  name: string;
  kind: CatalogSourceKind;
  adapter_key: string;
  endpoint: string;
  is_enabled?: boolean;
  country?: string | null;
  currency?: string;
  reliability_rating?: number;
  rate_limit_per_min?: number;
  timeout_seconds?: number;
  auth?: Record<string, unknown> | null;
  config?: Record<string, unknown> | null;
  notes?: string | null;
}

export interface ExternalProductResult {
  source_id: number;
  source_name: string;
  adapter_key: string;
  product_name: string;
  description: string | null;
  sku: string | null;
  url: string | null;
  image_url: string | null;
  unit_price: string;
  currency: string;
  lead_time_days: number;
  available_stock: number;
  minimum_order_quantity: number;
  rating: string;
}

export interface TestSourceResponse {
  source_id: number;
  source_name: string;
  adapter_key: string;
  query: string;
  elapsed_ms: number;
  ok: boolean;
  error: string | null;
  results: ExternalProductResult[];
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }
  if (!response.ok) {
    const detail =
      typeof payload === "object" && payload !== null && "detail" in payload
        ? (payload as { detail: unknown }).detail
        : payload;
    throw new Error(
      typeof detail === "string" ? detail : `${response.status} ${response.statusText}`,
    );
  }
  return payload as T;
}

export const api = {
  listAdapters: () => http<AdapterInfo[]>("/catalog-sources/adapters"),
  listSources: () => http<CatalogSource[]>("/catalog-sources"),
  createSource: (body: CatalogSourceInput) =>
    http<CatalogSource>("/catalog-sources", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateSource: (id: number, body: Partial<CatalogSourceInput>) =>
    http<CatalogSource>(`/catalog-sources/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteSource: (id: number) =>
    http<void>(`/catalog-sources/${id}`, { method: "DELETE" }),
  testSource: (id: number, query: string, limit = 5) =>
    http<TestSourceResponse>(`/catalog-sources/${id}/test`, {
      method: "POST",
      body: JSON.stringify({ query, limit }),
    }),
};
