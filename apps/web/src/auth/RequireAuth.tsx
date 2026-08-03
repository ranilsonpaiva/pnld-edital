import type { ReactNode } from "react";
import { useAuth } from "./AuthProvider";

/**
 * Gate for future protected screens.
 * Today AUTH is off, so children always render.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { enabled, canAccess, signInDev } = useAuth();

  if (!enabled) return children;

  if (!canAccess) {
    return (
      <div className="empty" style={{ paddingTop: 80 }}>
        <h2>Autenticação necessária</h2>
        <p>O modo autenticado está ligado, mas ainda sem provedor real.</p>
        <button type="button" className="btn" onClick={() => signInDev()}>
          Entrar (dev stub)
        </button>
      </div>
    );
  }

  return children;
}
