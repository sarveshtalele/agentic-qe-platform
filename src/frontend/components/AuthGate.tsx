"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, ReactNode, useContext, useEffect, useState } from "react";
import { api } from "../lib/api";
import { Spinner } from "./ui";

const AuthContext = createContext<{ user: any; signOut: () => void }>({ user: null, signOut: () => {} });
export const useAuth = () => useContext(AuthContext);

/** Nothing renders until the session is confirmed. The API enforces access; this only sends people to sign in. */
export function AuthGate({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const open = pathname === "/login";
  useEffect(() => {
    if (open) return;
    api("/auth/me").then(setUser).catch(() => router.replace("/login"));
  }, [open, pathname, router]);
  const signOut = async () => {
    await api("/auth/logout", { method: "POST" });
    setUser(null);
    router.replace("/login");
  };
  if (open) return <>{children}</>;
  if (!user) return <div className="flex min-h-screen items-center justify-center"><Spinner /></div>;
  return <AuthContext.Provider value={{ user, signOut }}>{children}</AuthContext.Provider>;
}

export function UserMenu() {
  const { user, signOut } = useAuth();
  if (!user) return null;
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-slate-600 dark:text-slate-400" data-testid="signed-in-user">{user.username}{user.role === "admin" ? " (admin)" : ""}</span>
      <button type="button" onClick={signOut} className="rounded-lg border border-slate-300 px-2.5 py-1.5 font-semibold hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800">Sign out</button>
    </div>
  );
}
