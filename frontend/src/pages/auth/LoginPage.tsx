import { zodResolver } from '@hookform/resolvers/zod';
import {
  ArrowRight,
  Eye,
  EyeOff,
  FileCheck2,
  Languages,
  LoaderCircle,
  LockKeyhole,
  Mail,
  ShieldCheck,
} from 'lucide-react';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Navigate, useLocation, useNavigate, type Location } from 'react-router';
import { z } from 'zod';

import { authApi } from '../../api/authApi';
import { getApiErrorMessage } from '../../api/errors';
import { ApplicationMark } from '../../components/common/ApplicationMark';
import { appConfig } from '../../config/app';
import { useAuthStore } from '../../store/authStore';

const loginSchema = z.object({
  email: z.string().min(1, 'Email is required.').email('Enter a valid email address.'),
  password: z.string().min(1, 'Password is required.'),
});

type LoginFormValues = z.infer<typeof loginSchema>;

interface LoginLocationState {
  from?: Location;
}

export function LoginPage() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const setAuth = useAuthStore((state) => state.setAuth);
  const [isPasswordVisible, setIsPasswordVisible] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const location = useLocation();
  const navigate = useNavigate();
  const {
    formState: { errors, isSubmitting },
    handleSubmit,
    register,
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: '',
      password: '',
    },
  });

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  const submitLogin = async (values: LoginFormValues): Promise<void> => {
    setServerError(null);

    try {
      const session = await authApi.login(values);
      setAuth(session);

      const state = location.state as LoginLocationState | null;
      const requestedPath = state?.from?.pathname;
      const destination =
        requestedPath?.startsWith('/') === true && requestedPath !== '/login'
          ? requestedPath
          : '/dashboard';
      navigate(destination, { replace: true });
    } catch (error: unknown) {
      setServerError(
        getApiErrorMessage(
          error,
          'Unable to sign in. Check your credentials and try again.',
        ),
      );
    }
  };

  return (
    <main className="grid min-h-screen bg-slate-50 lg:grid-cols-[minmax(0,0.92fr)_minmax(32rem,1.08fr)]">
      <section className="relative hidden overflow-hidden bg-slate-950 px-12 py-12 text-white lg:flex lg:flex-col">
        <div
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_18%_18%,rgba(37,99,235,0.42),transparent_32%),radial-gradient(circle_at_85%_80%,rgba(14,165,233,0.22),transparent_34%)]"
          aria-hidden="true"
        />
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.08] [background-image:linear-gradient(rgba(255,255,255,.32)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,.32)_1px,transparent_1px)] [background-size:48px_48px]"
          aria-hidden="true"
        />

        <div className="relative z-10">
          <ApplicationMark tone="dark" />
        </div>

        <div className="relative z-10 my-auto max-w-xl py-16">
          <span className="inline-flex items-center gap-2 rounded-full border border-blue-300/20 bg-blue-400/10 px-3 py-1.5 text-xs font-semibold text-blue-100">
            <ShieldCheck className="size-3.5" aria-hidden="true" />
            Secure document operations
          </span>
          <h1 className="mt-7 text-balance text-5xl font-semibold leading-[1.08] tracking-[-0.045em]">
            Clarity across every document and every language.
          </h1>
          <p className="mt-6 max-w-lg text-base leading-8 text-slate-300">
            A focused workspace for document identification, multilingual validation,
            and compliance review.
          </p>

          <div className="mt-10 grid gap-3 sm:grid-cols-3">
            {[
              { icon: FileCheck2, label: 'Document control' },
              { icon: Languages, label: 'Three languages' },
              { icon: LockKeyhole, label: 'Role-based access' },
            ].map(({ icon: Icon, label }) => (
              <div
                key={label}
                className="rounded-2xl border border-white/10 bg-white/[0.06] p-4 backdrop-blur"
              >
                <Icon className="size-5 text-blue-300" aria-hidden="true" />
                <p className="mt-3 text-xs font-medium text-slate-200">{label}</p>
              </div>
            ))}
          </div>
        </div>

        <p className="relative z-10 text-xs text-slate-500">
          Version {appConfig.version}
        </p>
      </section>

      <section className="relative flex min-h-screen items-center justify-center px-5 py-12 sm:px-8">
        <div
          className="pointer-events-none absolute inset-x-0 top-0 h-80 bg-[radial-gradient(circle_at_top,rgba(59,130,246,0.10),transparent_62%)] lg:hidden"
          aria-hidden="true"
        />

        <div className="relative w-full max-w-md">
          <div className="mb-10 lg:hidden">
            <ApplicationMark />
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-700">
              Welcome back
            </p>
            <h2 className="mt-3 text-3xl font-semibold tracking-[-0.035em] text-slate-950 sm:text-4xl">
              Sign in to your workspace
            </h2>
            <p className="mt-4 text-sm leading-6 text-slate-600">
              Document Control and Three-Language Compliance
            </p>
          </div>

          <div className="mt-9 rounded-3xl border border-slate-200/80 bg-white p-6 shadow-panel sm:p-8">
            <form
              className="space-y-5"
              onSubmit={(event) => void handleSubmit(submitLogin)(event)}
              noValidate
            >
              {serverError && (
                <div
                  className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm leading-6 text-rose-700"
                  role="alert"
                >
                  {serverError}
                </div>
              )}

              <div>
                <label className="text-sm font-semibold text-slate-800" htmlFor="email">
                  Email address
                </label>
                <div className="relative mt-2">
                  <Mail
                    className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-400"
                    aria-hidden="true"
                  />
                  <input
                    id="email"
                    type="email"
                    autoComplete="email"
                    aria-invalid={errors.email ? 'true' : 'false'}
                    aria-describedby={errors.email ? 'email-error' : undefined}
                    className="min-h-12 w-full rounded-xl border border-slate-200 bg-slate-50/80 py-3 pl-10 pr-4 text-sm text-slate-950 outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:bg-white focus:ring-4 focus:ring-blue-100"
                    placeholder="name@company.com"
                    {...register('email')}
                  />
                </div>
                {errors.email && (
                  <p id="email-error" className="mt-2 text-xs text-rose-600">
                    {errors.email.message}
                  </p>
                )}
              </div>

              <div>
                <label
                  className="text-sm font-semibold text-slate-800"
                  htmlFor="password"
                >
                  Password
                </label>
                <div className="relative mt-2">
                  <LockKeyhole
                    className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-400"
                    aria-hidden="true"
                  />
                  <input
                    id="password"
                    type={isPasswordVisible ? 'text' : 'password'}
                    autoComplete="current-password"
                    aria-invalid={errors.password ? 'true' : 'false'}
                    aria-describedby={errors.password ? 'password-error' : undefined}
                    className="min-h-12 w-full rounded-xl border border-slate-200 bg-slate-50/80 py-3 pl-10 pr-12 text-sm text-slate-950 outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:bg-white focus:ring-4 focus:ring-blue-100"
                    placeholder="Enter your password"
                    {...register('password')}
                  />
                  <button
                    type="button"
                    onClick={() => setIsPasswordVisible((visible) => !visible)}
                    className="absolute right-2 top-1/2 grid size-9 -translate-y-1/2 place-items-center rounded-lg text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600"
                    aria-label={isPasswordVisible ? 'Hide password' : 'Show password'}
                  >
                    {isPasswordVisible ? (
                      <EyeOff className="size-4" aria-hidden="true" />
                    ) : (
                      <Eye className="size-4" aria-hidden="true" />
                    )}
                  </button>
                </div>
                {errors.password && (
                  <p id="password-error" className="mt-2 text-xs text-rose-600">
                    {errors.password.message}
                  </p>
                )}
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-blue-700 px-5 text-sm font-semibold text-white shadow-lg shadow-blue-700/20 transition hover:bg-blue-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:opacity-65"
              >
                {isSubmitting ? (
                  <>
                    <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
                    Signing in...
                  </>
                ) : (
                  <>
                    Sign in
                    <ArrowRight className="size-4" aria-hidden="true" />
                  </>
                )}
              </button>
            </form>
          </div>

          <p className="mt-6 text-center text-xs leading-5 text-slate-500">
            {appConfig.name} · v{appConfig.version}
          </p>
        </div>
      </section>
    </main>
  );
}
