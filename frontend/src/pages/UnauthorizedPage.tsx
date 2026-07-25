import { ArrowLeft, ShieldX } from 'lucide-react';
import { Link } from 'react-router';

export function UnauthorizedPage() {
  return (
    <main className="grid min-h-screen place-items-center bg-slate-50 px-5 py-12">
      <section className="w-full max-w-lg rounded-3xl border border-slate-200 bg-white p-8 text-center shadow-panel sm:p-12">
        <div className="mx-auto grid size-14 place-items-center rounded-2xl bg-amber-50 text-amber-700">
          <ShieldX className="size-7" aria-hidden="true" />
        </div>
        <p className="mt-6 text-sm font-bold tracking-[0.2em] text-amber-700">403</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">
          Access denied
        </h1>
        <p className="mt-4 text-sm leading-7 text-slate-600">
          You do not have permission to access this page.
        </p>
        <Link
          to="/dashboard"
          className="mt-7 inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-blue-700 px-5 text-sm font-semibold text-white transition hover:bg-blue-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        >
          <ArrowLeft className="size-4" aria-hidden="true" />
          Back to dashboard
        </Link>
      </section>
    </main>
  );
}
