import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  // Cache Components (PPR) is off: every page here is session-gated and
  // reads live data, so there is nothing worth prerendering into a static
  // shell. Keeping classic dynamic rendering avoids "use cache" / Suspense
  // boilerplate the app doesn't need.
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
