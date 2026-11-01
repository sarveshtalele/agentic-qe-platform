import type { Metadata } from "next";
import { AuthGate } from "../components/AuthGate";
import { ToastProvider } from "../components/ui";
import "./globals.css";

export const metadata: Metadata = {
  title: "Agentic QE Platform — Agentic BA and QE workspace",
  description: "Requirements, code changes, bug scans, and governed test engineering on Microsoft Agent Framework.",
};

const themeScript = `try{var t=localStorage.getItem('atlas_theme');if(t==='light'){document.documentElement.classList.remove('dark');document.documentElement.classList.add('light')}}catch(e){}`;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="antialiased bg-slate-50 dark:bg-[#030712] text-slate-900 dark:text-slate-100 min-h-screen">
        <ToastProvider><AuthGate>{children}</AuthGate></ToastProvider>
      </body>
    </html>
  );
}
