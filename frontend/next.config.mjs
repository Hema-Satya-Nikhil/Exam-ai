/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    typedRoutes: true
  },
  eslint: {
    // The repository has not historically run ESLint during builds; lint is
    // available as an explicit local check (`npm run lint`).
    ignoreDuringBuilds: true
  }
};

export default nextConfig;
