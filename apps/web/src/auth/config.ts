/** Auth is off in MVP. Flip VITE_AUTH_ENABLED=true when wiring a provider. */
export const authConfig = {
  enabled: import.meta.env.VITE_AUTH_ENABLED === "true",
  provider: (import.meta.env.VITE_AUTH_PROVIDER as string | undefined) ?? "none",
};

export type AuthUser = {
  id: string;
  name: string;
  email: string;
  role: "reviewer" | "admin";
};
