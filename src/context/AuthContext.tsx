import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react';

import type { User } from '../types';

import {
  login as apiLogin,
  logout as apiLogout,
  restoreSession,
  changePassword as apiChangePassword,
} from '../api/auth';

import { getToken } from '../api/client';

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  restoring: boolean;
  error: string | null;
  mustChangePassword: boolean;

  login: (
    email: string,
    password: string
  ) => Promise<void>;

  changePassword: (
    newPassword: string
  ) => Promise<void>;

  logout: () => void;
}

const AuthContext =
  createContext<AuthContextValue | undefined>(
    undefined
  );

export function AuthProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [user, setUser] =
    useState<User | null>(null);

  const [loading, setLoading] =
    useState(false);

  const [restoring, setRestoring] =
    useState(true);

  const [error, setError] =
    useState<string | null>(null);

  const [mustChangePassword, setMustChangePassword] =
    useState(false);

  useEffect(() => {
    async function restore() {
      if (!getToken()) {
        setRestoring(false);
        return;
      }

      try {
        const restoredUser =
          await restoreSession();

        setUser(restoredUser);

        /*
         * /auth/me returns the current user but does not
         * need to expose the temporary-password flag after
         * the session has been established.
         *
         * The flag is therefore primarily handled during
         * login.
         */
        setMustChangePassword(false);
      } finally {
        setRestoring(false);
      }
    }

    restore();
  }, []);

  async function login(
    email: string,
    password: string
  ) {
    setLoading(true);
    setError(null);

    try {
      const response = await apiLogin(
        email,
        password
      );

      setUser(response.user);

      setMustChangePassword(
        Boolean(response.mustChangePassword)
      );
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : 'Login failed'
      );

      throw e;
    } finally {
      setLoading(false);
    }
  }

  async function changePassword(
    newPassword: string
  ) {
    setLoading(true);
    setError(null);

    try {
      await apiChangePassword(newPassword);

      setMustChangePassword(false);
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : 'Unable to change password'
      );

      throw e;
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    apiLogout();

    setUser(null);
    setMustChangePassword(false);
    setError(null);
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        restoring,
        error,
        mustChangePassword,
        login,
        changePassword,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);

  if (!ctx) {
    throw new Error(
      'useAuth must be used within AuthProvider'
    );
  }

  return ctx;
}