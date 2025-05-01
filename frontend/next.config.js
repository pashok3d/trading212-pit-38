/** @type {import('next').NextConfig} */
const nextConfig = {
    reactStrictMode: true,
    // API routes proxy for development
    async rewrites() {
        return [
            {
                source: '/api/:path*',
                destination: 'http://localhost:8000/api/:path*', // Proxy to backend
            },
        ];
    },
};

module.exports = nextConfig;