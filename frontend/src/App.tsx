import {
  ArrowUpRight,
  FileCheck2,
  Languages,
  ScanSearch,
  ShieldCheck,
} from 'lucide-react';

import { ApplicationMark } from './components/common/ApplicationMark';
import { HealthStatusCard } from './components/common/HealthStatusCard';
import { appConfig } from './config/app';

const capabilities = [
  {
    icon: ScanSearch,
    title: 'Identify',
    description: 'Turn document filenames and metadata into structured records.',
  },
  {
    icon: Languages,
    title: 'Validate',
    description: 'Check Indonesian, English, and Mandarin content coverage.',
  },
  {
    icon: FileCheck2,
    title: 'Control',
    description: 'Surface findings and support a clear compliance workflow.',
  },
] as const;

export default function App() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-slate-50 text-slate-900">
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-[34rem] bg-[radial-gradient(circle_at_15%_0%,rgba(59,130,246,0.13),transparent_36%),radial-gradient(circle_at_82%_9%,rgba(14,165,233,0.11),transparent_28%)]"
        aria-hidden="true"
      />
      <div
        className="pointer-events-none absolute -right-24 top-48 size-80 animate-float rounded-full border border-blue-100/80 bg-white/40 blur-sm"
        aria-hidden="true"
      />

      <header className="relative z-10 border-b border-slate-200/70 bg-white/65 backdrop-blur-xl">
        <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-5 sm:px-8 lg:px-12">
          <ApplicationMark />
          <div className="flex items-center gap-2 rounded-full border border-slate-200/80 bg-white/80 px-3 py-1.5 text-xs font-semibold text-slate-600 shadow-sm">
            <span className="hidden sm:inline">Foundation release</span>
            <span className="hidden text-slate-300 sm:inline">/</span>
            <span>v{appConfig.version}</span>
          </div>
        </div>
      </header>

      <main className="relative z-10">
        <section className="mx-auto grid max-w-7xl items-center gap-14 px-5 py-16 sm:px-8 sm:py-20 lg:grid-cols-[minmax(0,1.08fr)_minmax(22rem,0.72fr)] lg:gap-20 lg:px-12 lg:py-28">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-blue-200/70 bg-blue-50/80 px-3 py-1.5 text-xs font-semibold text-blue-800">
              <ShieldCheck className="size-3.5" aria-hidden="true" />
              Built for Document Control teams
            </div>

            <h1 className="mt-7 max-w-3xl text-balance text-4xl font-semibold leading-[1.07] tracking-[-0.04em] text-slate-950 sm:text-5xl lg:text-[3.65rem]">
              Documents you can verify with confidence.
            </h1>
            <p className="mt-6 max-w-2xl text-pretty text-base leading-8 text-slate-600 sm:text-lg">
              {appConfig.name} creates one clear path from document identification to
              trilingual compliance review.
            </p>

            <div className="mt-10 grid gap-4 sm:grid-cols-3">
              {capabilities.map(({ description, icon: Icon, title }) => (
                <article
                  key={title}
                  className="group rounded-2xl border border-slate-200/80 bg-white/60 p-4 backdrop-blur-sm transition duration-300 hover:-translate-y-0.5 hover:border-blue-200 hover:bg-white"
                >
                  <div className="flex items-center justify-between">
                    <div className="grid size-9 place-items-center rounded-xl bg-blue-50 text-blue-700">
                      <Icon className="size-4" strokeWidth={1.9} aria-hidden="true" />
                    </div>
                    <ArrowUpRight
                      className="size-4 text-slate-300 transition group-hover:text-blue-500"
                      aria-hidden="true"
                    />
                  </div>
                  <h2 className="mt-4 text-sm font-semibold text-slate-950">{title}</h2>
                  <p className="mt-1.5 text-xs leading-5 text-slate-500">
                    {description}
                  </p>
                </article>
              ))}
            </div>
          </div>

          <div className="relative">
            <div
              className="absolute -inset-5 -z-10 rounded-[2.25rem] bg-gradient-to-br from-blue-200/30 via-white to-cyan-100/40 blur-xl"
              aria-hidden="true"
            />
            <HealthStatusCard />
            <p className="mt-4 text-center text-xs leading-5 text-slate-500">
              Connection is checked automatically every 30 seconds.
            </p>
          </div>
        </section>
      </main>

      <footer className="relative z-10 border-t border-slate-200/70">
        <div className="mx-auto flex max-w-7xl flex-col gap-2 px-5 py-7 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between sm:px-8 lg:px-12">
          <p>{appConfig.shortName}</p>
          <p>Secure foundation for compliant document operations.</p>
        </div>
      </footer>
    </div>
  );
}
