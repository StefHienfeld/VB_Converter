/**
 * Frontend configuration for VB_Converter.
 *
 * Environment-driven configuration using Vite's import.meta.env.
 * All VITE_* variables are available at build time.
 */

type Environment = "development" | "test" | "acceptance" | "production";

interface Config {
  environment: Environment;
  apiBaseUrl: string;
  appVersion: string;
  features: {
    aiExtensions: boolean;
  };
}

/**
 * Get configuration based on environment variables.
 */
const getConfig = (): Config => {
  const env = (import.meta.env.VITE_ENVIRONMENT || "development") as Environment;

  // API URL can be overridden, or defaults based on environment
  const defaultApiUrls: Record<Environment, string> = {
    development: "http://localhost:8000",
    test: "http://localhost:8000",
    acceptance: "http://localhost:8000",
    production: "http://localhost:8000",
  };

  return {
    environment: env,
    apiBaseUrl: import.meta.env.VITE_API_URL || defaultApiUrls[env],
    appVersion: import.meta.env.VITE_APP_VERSION || "3.1.0",
    features: {
      aiExtensions: import.meta.env.VITE_FEATURE_AI === "true",
    },
  };
};

export const config = getConfig();
export default config;
