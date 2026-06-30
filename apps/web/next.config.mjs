/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // AI endpoints (recommend / panel / debate …) call `claude -p` and routinely take
  // 60–140s. Next's rewrite proxy defaults to a 30s timeout, which surfaced to the
  // browser as a raw "500: Internal Server Error" on every slow generate. Raise it well
  // past the slowest LLM call so the browser receives the real backend response.
  experimental: { proxyTimeout: 300_000 },
  // Proxy API calls to the local FastAPI backend so the browser can use same-origin /api.
  async rewrites() {
    return [{ source: "/api/:path*", destination: "http://localhost:8000/:path*" }];
  },
};

export default nextConfig;
