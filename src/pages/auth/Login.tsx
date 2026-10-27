import { useState } from 'react';
import { Link, Navigate, useLocation } from 'react-router-dom';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../../components/common/Button';

export default function Login() {
  const { user, login, loading, error } = useAuth();
  const location = useLocation();

  const studentLogin = location.pathname === '/student/login';

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  if (user) {
    return <Navigate to={`/${user.role}`} replace />;
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    try {
      await login(email.trim(), password);
    } catch {
      // The authentication error is displayed below the form.
    }
  }

  return (
    <div className="min-h-screen bg-[#090c12] px-5 py-8 text-white">
      <div className="mx-auto flex w-full max-w-md flex-col items-center pt-1 sm:pt-5">
        <Link
          to="/login"
          className="mb-8 flex items-center gap-2"
          aria-label="CoreSight home"
        >
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-400 to-blue-500">
            <span className="h-2.5 w-2.5 rounded-full bg-[#09101b]" />
          </span>

          <span className="font-display text-xl font-semibold tracking-tight">
            CoreSight
          </span>
        </Link>

        <div className="w-full rounded-2xl border border-[#263247] bg-[#111620] p-6 sm:p-7">
          <h1 className="font-display text-xl font-semibold">
            {studentLogin ? 'Student sign in' : 'Sign in'}
          </h1>

          <p className="mt-2 text-sm leading-relaxed text-[#94a3b8]">
            {studentLogin
              ? 'Sign in using the student account credentials provided to you.'
              : 'Welcome back. Sign in to continue to your CoreSight account.'}
          </p>

          <form onSubmit={handleSubmit} className="mt-6 space-y-5">
            <div>
              <label
                htmlFor="email"
                className="mb-2 block text-xs font-medium text-[#a8b7d0]"
              >
                Email
              </label>

              <input
                id="email"
                name="email"
                type="email"
                autoComplete="username"
                placeholder="you@coresight.edu"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="w-full rounded-lg border border-[#263247] bg-[#1a2130] px-3 py-3 text-sm text-white outline-none transition placeholder:text-[#8492a8] focus:border-cyan-400"
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="mb-2 block text-xs font-medium text-[#a8b7d0]"
              >
                Password
              </label>

              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                placeholder="Enter your password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="w-full rounded-lg border border-[#263247] bg-[#1a2130] px-3 py-3 text-sm text-white outline-none transition placeholder:text-[#8492a8] focus:border-cyan-400"
              />
            </div>

            <div className="flex justify-end">
              <Link
                to="/forgot-password"
                className="text-xs font-medium text-cyan-400 hover:text-cyan-300"
              >
                Forgot password?
              </Link>
            </div>

            {error && (
              <div
                role="alert"
                className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2.5 text-sm text-red-300"
              >
                {error}
              </div>
            )}

            <Button
              type="submit"
              className="w-full"
              disabled={loading}
            >
              {loading ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>
        </div>

        <div className="mt-5 space-y-3 text-center text-xs leading-relaxed text-[#94a3b8]">
          <p>
            Are you a faculty member?{' '}
            <Link
              to="/faculty/register"
              className="font-medium text-cyan-400 hover:text-cyan-300"
            >
              Request faculty access
            </Link>
          </p>

          <p>
            Are you a student?{' '}
            {studentLogin ? (
              <Link
                to="/login"
                className="font-medium text-cyan-400 hover:text-cyan-300"
              >
                Go to main sign in
              </Link>
            ) : (
              <Link
                to="/student/login"
                className="font-medium text-cyan-400 hover:text-cyan-300"
              >
                Student sign in
              </Link>
            )}
          </p>

          <p className="max-w-sm text-[11px] text-[#718096]">
            Students registered through the college registration form should
            use the email and temporary password provided to them.
          </p>
        </div>
      </div>
    </div>
  );
}
