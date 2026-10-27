import type { User } from '../types';
import { request, setToken } from './client';

export interface LoginResponse {
  user: User;
  accessToken: string;
  mustChangePassword: boolean;
}

export async function login(
  email: string,
  password: string
): Promise<LoginResponse> {
  const data = await request<LoginResponse>('/auth/login', {
    body: {
      email: email.trim().toLowerCase(),
      password,
    },
  });

  setToken(data.accessToken);

  return data;
}

export function logout() {
  setToken(null);
}

export async function restoreSession(): Promise<User | null> {
  try {
    return await request<User>('/auth/me');
  } catch {
    setToken(null);
    return null;
  }
}

export async function fetchCurrentUser(
  _id: string
): Promise<User | null> {
  return restoreSession();
}

export interface ForgotPasswordPayload {
  email: string;
}

export interface ResetPasswordPayload {
  token: string;
  new_password: string;
}

export function forgotPassword(
  payload: ForgotPasswordPayload
) {
  return request<{ message: string }>(
    '/auth/forgot-password',
    {
      method: 'POST',
      body: {
        email: payload.email.trim().toLowerCase(),
      },
    }
  );
}

export function resetPassword(
  payload: ResetPasswordPayload
) {
  return request<{ message: string }>(
    '/auth/reset-password',
    {
      method: 'POST',
      body: payload,
    }
  );
}

export async function changePassword(
  newPassword: string
) {
  return request<{
    message: string;
    mustChangePassword: boolean;
  }>('/auth/change-password', {
    method: 'POST',
    body: {
      new_password: newPassword,
    },
  });
}