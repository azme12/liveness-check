"use client";

import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

export type AppEnvironment = "test" | "live";

type EnvContextValue = {
  env: AppEnvironment;
  setEnv: (env: AppEnvironment) => void;
  liveEnabled: boolean;
  setLiveEnabled: (v: boolean) => void;
  /** Mongo access field: sandbox | live */
  access: "sandbox" | "live";
  label: "Test" | "Live";
};

const EnvContext = createContext<EnvContextValue>({
  env: "test",
  setEnv: () => undefined,
  liveEnabled: false,
  setLiveEnabled: () => undefined,
  access: "sandbox",
  label: "Test",
});

export function EnvironmentProvider({ children }: { children: ReactNode }) {
  const [env, setEnvState] = useState<AppEnvironment>("test");
  const [liveEnabled, setLiveEnabled] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("trustanova_env");
    const enabled = localStorage.getItem("trustanova_live_enabled") === "1";
    setLiveEnabled(enabled);
    if (stored === "live" && enabled) setEnvState("live");
    else {
      setEnvState("test");
      localStorage.setItem("trustanova_env", "test");
    }
  }, []);

  const setEnv = useCallback(
    (next: AppEnvironment) => {
      if (next === "live" && !liveEnabled) return;
      setEnvState(next);
      localStorage.setItem("trustanova_env", next);
    },
    [liveEnabled],
  );

  const updateLiveEnabled = useCallback((v: boolean) => {
    setLiveEnabled(v);
    localStorage.setItem("trustanova_live_enabled", v ? "1" : "0");
    if (!v) {
      setEnvState("test");
      localStorage.setItem("trustanova_env", "test");
    }
  }, []);

  return (
    <EnvContext.Provider
      value={{
        env,
        setEnv,
        liveEnabled,
        setLiveEnabled: updateLiveEnabled,
        access: env === "test" ? "sandbox" : "live",
        label: env === "test" ? "Test" : "Live",
      }}
    >
      {children}
    </EnvContext.Provider>
  );
}

export function useEnvironment() {
  return useContext(EnvContext);
}
