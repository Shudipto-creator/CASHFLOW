import React, { createContext, useContext, useEffect, useState } from "react";
import { getProcessingMode, setProcessingMode } from "../services/api";

const ModeContext = createContext({
  mode: "aws",
  modes: [],
  aws: {},
  local: {},
  loading: true,
  setMode: async () => {},
  refresh: async () => {},
});

export const ModeProvider = ({ children }) => {
  const storedMode = (() => {
    try {
      return localStorage.getItem('cashflow-processing-mode') || 'aws';
    } catch (e) {
      console.warn('Failed to read stored processing mode:', e);
      return 'aws';
    }
  })();
  const [mode, setModeState] = useState(storedMode);
  const [modes, setModes] = useState([
    {
      id: "aws",
      label: "AWS Mode",
      description: "Amazon Bedrock Nova agents, Titan embeddings, Sonic TTS",
    },
    {
      id: "local",
      label: "Local Mode",
      description: "Local sklearn classifier/analyzer + Ollama chat",
    },
  ]);
  const [aws, setAws] = useState({});
  const [local, setLocal] = useState({});
  const [loading, setLoading] = useState(true);

  const refresh = async (signal) => {
    try {
      const res = await getProcessingMode({ signal });
      const data = res.data || {};
      const nextMode = data.mode || data.active_mode || "aws";
      setModeState(nextMode);
      try {
        localStorage.setItem("cashflow-processing-mode", nextMode);
      } catch (e) {
        console.warn("Failed to store processing mode:", e);
      }
      if (Array.isArray(data.modes) && data.modes.length) {
        setModes(data.modes);
      }
      setAws(data.aws || {});
      setLocal(data.local || {});
    } catch (err) {
      if (err.name === "CanceledError") return;
      console.warn("Failed to load processing mode:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const controller = new AbortController();
    refresh(controller.signal);
    return () => controller.abort();
  }, []);

  const setMode = async (nextMode) => {
    if (!nextMode || nextMode === mode) return;
    setLoading(true);
    try {
      const res = await setProcessingMode(nextMode);
      const data = res.data || {};
      const applied = data.mode || nextMode;
      setModeState(applied);
      try {
        localStorage.setItem("cashflow-processing-mode", applied);
      } catch (e) {
        console.warn("Failed to store processing mode:", e);
      }
      setAws(data.aws || {});
      setLocal(data.local || {});
      if (Array.isArray(data.modes) && data.modes.length) {
        setModes(data.modes);
      }
    } catch (err) {
      console.error("Failed to update processing mode:", err);
      alert(
        err.response?.data?.detail ||
          "Failed to switch processing mode. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <ModeContext.Provider
      value={{ mode, modes, aws, local, loading, setMode, refresh }}
    >
      {children}
    </ModeContext.Provider>
  );
};

export const useMode = () => useContext(ModeContext);

export default ModeContext;
