/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Emit a self-contained server bundle (.next/standalone) so the runner image
  // ships only the traced node_modules + server, not the full workspace.
  output: "standalone",
};

export default nextConfig;
