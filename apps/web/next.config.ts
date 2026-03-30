import type { NextConfig } from "next";

const backendBase =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_BASE ??
  process.env.API_BASE_URL ??
  "http://127.0.0.1:8010";

const nextConfig: NextConfig = {
  distDir: process.env.NODE_ENV === "development" ? ".next-dev" : ".next",
  reactStrictMode: true,
  async rewrites() {
    const normalizedBackendBase = backendBase.replace(/\/$/, "");
    return [
      {
        source: "/api/proxy/:path*",
        destination: `${normalizedBackendBase}/:path*`,
      },
    ];
  },
};

export default nextConfig;
