import type { NextConfig } from "next";

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "standalone",
  // Architect calls Claude (15-40s on cold cache); the default 30s proxy
  // timeout would 500 the request before the SDK finishes.
  experimental: {
    proxyTimeout: 240_000,
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
