import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone is for Docker self-host only. Vercel builds without it.
  ...(process.env.DOCKER_BUILD === "1" ? { output: "standalone" as const } : {}),
};

export default nextConfig;
