import type { NextConfig } from "next";

// Atlas sends no usage data to third parties.
process.env.COPILOTKIT_TELEMETRY_DISABLED = "true";

const backend = process.env.ATLAS_BACKEND_URL || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  distDir: process.env.ATLAS_DIST_DIR || ".next",
  // Azure startup sets this: the server then runs from a small self-contained folder.
  ...(process.env.ATLAS_STANDALONE ? { output: "standalone" as const } : {}),
  // gzip holds back event streams until they end, which would hide live run activity. The app runs on loopback, so it gains nothing.
  compress: false,
  // Long clones and large ZIP uploads go through this proxy.
  experimental: { proxyTimeout: 900_000, proxyClientMaxBodySize: "200mb" },
  async rewrites() {
    // fallback runs after dynamic routes, so /api/copilotkit reaches its own route handler instead of the backend
    return { beforeFiles: [], afterFiles: [], fallback: [{ source: "/api/:path*", destination: `${backend}/api/:path*` }] };
  },
};

export default nextConfig;
