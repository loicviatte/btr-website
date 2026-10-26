/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: false,
  images: { unoptimized: true },
  async headers() {
    return [{ source: '/assets/:path*', headers: [{ key: 'Cache-Control', value: 'public, max-age=31536000, immutable' }] }];
  },
};
export default nextConfig;
