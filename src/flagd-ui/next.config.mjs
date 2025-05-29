/** @type {import('next').NextConfig} */

const nextConfig = {
  basePath: "/feature",
  reactStrictMode: true,
  output: 'standalone',
  compiler: {
    styledComponents: true,
  },
};

export default nextConfig;
