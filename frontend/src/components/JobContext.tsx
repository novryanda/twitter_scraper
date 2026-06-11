"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
  ReactNode,
} from "react";

// ── Types ─────────────────────────────────────────────────────────────────────
export type JobType = "user_tweets" | "replies" | "search" | "profile" | "batch";

export interface ActiveJob {
  id: string;           // unik per job
  type: JobType;
  label: string;        // deskripsi singkat, mis: "@gibran_tweet — User Tweets"
  startedAt: Date;
}

interface JobContextValue {
  activeJob: ActiveJob | null;
  isRunning: boolean;
  startJob: (type: JobType, label: string) => string;   // return job id
  finishJob: (id: string) => void;
}

// ── Context ───────────────────────────────────────────────────────────────────
const JobContext = createContext<JobContextValue>({
  activeJob: null,
  isRunning: false,
  startJob: () => "",
  finishJob: () => {},
});

export const useJob = () => useContext(JobContext);

// ── Provider ──────────────────────────────────────────────────────────────────
export function JobProvider({ children }: { children: ReactNode }) {
  const [activeJob, setActiveJob] = useState<ActiveJob | null>(null);
  const jobIdRef = useRef<string>("");

  const startJob = useCallback((type: JobType, label: string): string => {
    const id = `${type}_${Date.now()}`;
    jobIdRef.current = id;
    setActiveJob({ id, type, label, startedAt: new Date() });
    return id;
  }, []);

  const finishJob = useCallback((id: string) => {
    // Hanya clear kalau id cocok — cegah race condition
    setActiveJob((prev) => (prev?.id === id ? null : prev));
  }, []);

  return (
    <JobContext.Provider value={{
      activeJob,
      isRunning: activeJob !== null,
      startJob,
      finishJob,
    }}>
      {children}
    </JobContext.Provider>
  );
}