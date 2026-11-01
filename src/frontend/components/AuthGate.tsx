"use client";

import Link from "next/link";
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

/** The tightest figure a person can run into: today's limit or the overall allocation. */
function tokensLeft(user: any): { left: number; limit: number; label: string } | null {
  const options = [];
  if (user.usage?.day?.limit != null) options.push({ limit: user.usage.day.limit, used: user.usage.day.used, label: "today" });
  if (user.token_limit != null) options.push({ limit: user.token_limit, used: user.tokens_used, label: "of your allocation" });
  const tightest = options.sort((a, b) => a.limit - a.used - (b.limit - b.used))[0];
  return tightest ? { left: Math.max(0, tightest.limit - tightest.used), limit: tightest.limit, label: tightest.label } : null;
}

export function UserMenu() {
  const { user: signedIn, signOut } = useAuth();
  const [user, setUser] = useState<any>(signedIn);
  useEffect(() => {
    setUser(signedIn);
    if (!signedIn || signedIn.role === "admin") return;
    const timer = setInterval(() => api("/auth/me").then(setUser).catch(() => {}), 30000);
    return () => clearInterval(timer);
  }, [signedIn]);
  if (!user) return null;
  const left = user.role === "admin" ? null : tokensLeft(user);
  const warn = left !== null && left.left <= left.limit * 0.2;
  return (
    <div className="flex items-center gap-2 text-xs">
      {left && <span data-testid="tokens-left" role={warn ? "alert" : undefined} className={warn ? "rounded-md bg-amber-500/15 px-2 py-1 font-semibold text-amber-600 dark:text-amber-400" : "text-slate-500"}>{left.left.toLocaleString()} tokens left {left.label}{warn ? (left.left === 0 ? ". Limit reached" : ". Over 80% used") : ""}</span>}
      <span className="text-slate-600 dark:text-slate-400" data-testid="signed-in-user">{user.username}{user.role === "admin" ? " (admin)" : ""}</span>
      <Link href="/account" className="rounded-lg border border-slate-300 px-2.5 py-1.5 font-semibold hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800">Account</Link>
      <button type="button" onClick={signOut} className="rounded-lg border border-slate-300 px-2.5 py-1.5 font-semibold hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800">Sign out</button>
    </div>
  );
}
