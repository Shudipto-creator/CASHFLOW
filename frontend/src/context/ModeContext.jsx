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
  const [mode, setModeState] = useState(
    () => localStorage.getItem("cfone-processing-mode") || "aws",
  );
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

  const refresh = async () => {
    try {
      const res = await getProcessingMode();
      const data = res.data || {};
      const nextMode = data.mode || data.active_mode || "aws";
      setModeState(nextMode);
      localStorage.setItem("cfone-processing-mode", nextMode);
      if (Array.isArray(data.modes) && data.modes.length) {
        setModes(data.modes);
      }
      setAws(data.aws || {});
      setLocal(data.local || {});
    } catch (err) {
      console.warn("Failed to load processing mode:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const setMode = async (nextMode) => {
    if (!nextMode || nextMode === mode) return;
    setLoading(true);
    try {
      const res = await setProcessingMode(nextMode);
      const data = res.data || {};
      const applied = data.mode || nextMode;
      setModeState(applied);
      localStorage.setItem("cfone-processing-mode", applied);
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
