import { Link } from "react-router-dom";

export default function DashboardPage() {
  return (
    <section className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Panel de operaciones</h2>
        <p className="text-slate-400 text-sm mt-1">
          El motor de procura combina catálogos locales con fuentes externas
          configurables. La API está disponible bajo{" "}
          <code className="text-emerald-400">/api</code>.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Link
          to="/sources"
          className="rounded-lg border border-slate-800 bg-slate-900 p-5 hover:border-emerald-500/40 hover:bg-slate-900/60 transition-colors"
        >
          <h3 className="font-medium text-emerald-300">Fuentes externas</h3>
          <p className="text-sm text-slate-400 mt-1">
            Gestiona el pool de proveedores web/email que el agente puede consultar.
          </p>
        </Link>
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-5 opacity-70">
          <h3 className="font-medium text-slate-200">Órdenes de compra</h3>
          <p className="text-sm text-slate-400 mt-1">
            En construcción. Próximo: listado, aprobación y descarga de PDFs.
          </p>
        </div>
      </div>
    </section>
  );
}
