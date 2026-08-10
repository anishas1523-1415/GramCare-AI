import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // `standalone` output is for the self-hosted Docker image (docker-compose /
  // Render node runtime). On Vercel it must be OFF — Vercel uses its own
  // serverless output, and a standalone build deploys with no routable pages
  // (the production 404-at-root bug). The Dockerfile sets DOCKER_BUILD=1.
  output: process.env.DOCKER_BUILD === "1" ? "standalone" : undefined,
};

export default nextConfig;
