import { ArrowLeft, FileQuestion } from 'lucide-react';
import { Link } from 'react-router';

import { useAuthStore } from '../store/authStore';

export function NotFoundPage() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const returnPath = isAuthenticated ? '/dashboard' : '/login';

  return (
    <main className="grid min-h-screen place-items-center bg-slate-50 px-5 py-12">
      <section className="w-full max-w-lg text-center">
        <div className="mx-auto grid size-16 place-items-center rounded-3xl border border-slate-200 bg-white text-blue-700 shadow-sm">
          <FileQuestion className="size-8" aria-hidden="true" />
        </div>
        <p className="mt-7 text-sm font-bold tracking-[0.2em] text-blue-700">404</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">
          Page not found
        </h1>
        <p className="mt-4 text-sm leading-7 text-slate-600">
          The page you requested does not exist or may have moved.
        </p>
        <Link
          to={returnPath}
          className="mt-7 inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-slate-950 px-5 text-sm font-semibold text-white transition hover:bg-slate-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        >
          <ArrowLeft className="size-4" aria-hidden="true" />
          {isAuthenticated ? 'Back to dashboard' : 'Go to sign in'}
        </Link>
      </section>
    </main>
  );
}
