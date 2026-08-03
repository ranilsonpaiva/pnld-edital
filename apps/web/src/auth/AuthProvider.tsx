import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { authConfig, type AuthUser } from "./config";

type AuthState = {
  enabled: boolean;
  user: AuthUser | null;
  /** Placeholder until a real provider is connected. */
  signInDev: (user?: Partial<AuthUser>) => void;
  signOut: () => void;
  canAccess: boolean;
};

const AuthContext = createContext<AuthState | null>(null);

const defaultDevUser: AuthUser = {
  id: "dev-reviewer",
  name: "Revisor local",
  email: "revisor@local.dev",
  role: "reviewer",
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);

  const signInDev = useCallback((partial?: Partial<AuthUser>) => {
    setUser({ ...defaultDevUser, ...partial });
  }, []);

  const signOut = useCallback(() => setUser(null), []);

  const value = useMemo<AuthState>(
    () => ({
      enabled: authConfig.enabled,
      user,
      signInDev,
      signOut,
      // When auth is disabled, everyone can access.
      canAccess: !authConfig.enabled || user !== null,
    }),
    [user, signInDev, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
