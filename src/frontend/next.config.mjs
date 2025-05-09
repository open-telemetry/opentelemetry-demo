export default {
  reactStrictMode: true,
  devIndicators: {
    buildActivity: false,
    buildActivityPosition: 'bottom-right',
  },
  // 禁用 React 开发覆盖层
  webpack: (config, { dev }) => {
    if (dev) {
      config.devServer = {
        client: {
          overlay: false, // 禁用全屏错误覆盖层
        },
      };
    }
    return config;
  },
};