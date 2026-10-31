import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Agentic QE Platform — Autonomous SDLC & Quality Engineering",
  description: "Enterprise Multi-Agent Quality Engineering & Autonomous SDLC Platform (MAF + Agentic-QE).",
  generator: "ForgeSDLC MAF Agentic-QE",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <head>
        <meta name="generator" content="ForgeSDLC MAF Agentic-QE" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="antialiased bg-slate-50 dark:bg-[#030712] text-slate-900 dark:text-slate-100 min-h-screen">
        {children}
      </body>
    </html>
  );
}
