export type AuthUser = {
  email: string;
};

export type AuthResult =
  | { success: true; user: AuthUser }
  | { success: false; message: string };

import { API_BASE } from "./api";

const normalizeEmail = (email: string) => email.trim().toLowerCase();
const callAuthEndpoint = async (
  endpoint: "register" | "login",
  email: string,
  password: string
): Promise<AuthResult> => {
  const normalized = normalizeEmail(email);
  if (!normalized || !password) {
    return { success: false, message: "Enter an email and password." };
  }

  try {
    const response = await fetch(`${API_BASE}/auth/${endpoint}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ email: normalized, password }),
    });

    if (!response.ok) {
      const data = await response.json().catch(() => null);
      return {
        success: false,
        message: data?.message || `Auth server error: ${response.status}`,
      };
    }

    return (await response.json()) as AuthResult;
  } catch (error) {
    return {
      success: false,
      message: "Unable to reach the auth server. Make sure it is running.",
    };
  }
};

export const registerUser = async (email: string, password: string): Promise<AuthResult> => {
  return await callAuthEndpoint("register", email, password);
};

export const loginUser = async (email: string, password: string): Promise<AuthResult> => {
  return await callAuthEndpoint("login", email, password);
};
