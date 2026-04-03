import { create } from 'zustand';
import { Signal, Position, Agent, PerformanceMetrics } from '@/types';

interface AppState {
  // UI State
  activeTab: string;
  isMobileMenuOpen: boolean;

  // Data State
  signals: Signal[];
  positions: Position[];
  agents: Agent[];
  performance: PerformanceMetrics | null;

  // Connection State
  isConnected: boolean;
  lastUpdate: string | null;

  // Actions
  setActiveTab: (tab: string) => void;
  setMobileMenuOpen: (open: boolean) => void;
  setSignals: (signals: Signal[]) => void;
  setPositions: (positions: Position[]) => void;
  setAgents: (agents: Agent[]) => void;
  setPerformance: (metrics: PerformanceMetrics) => void;
  setConnected: (connected: boolean) => void;
  setLastUpdate: (time: string) => void;
  addSignal: (signal: Signal) => void;
  updatePosition: (position: Position) => void;
}

export const useAppStore = create<AppState>((set) => ({
  // Initial state
  activeTab: 'overview',
  isMobileMenuOpen: false,
  signals: [],
  positions: [],
  agents: [],
  performance: null,
  isConnected: false,
  lastUpdate: null,

  // Actions
  setActiveTab: (tab) => set({ activeTab: tab }),
  setMobileMenuOpen: (open) => set({ isMobileMenuOpen: open }),
  setSignals: (signals) => set({ signals }),
  setPositions: (positions) => set({ positions }),
  setAgents: (agents) => set({ agents }),
  setPerformance: (metrics) => set({ performance: metrics }),
  setConnected: (connected) => set({ isConnected: connected }),
  setLastUpdate: (time) => set({ lastUpdate: time }),
  addSignal: (signal) => set((state) => ({
    signals: [signal, ...state.signals].slice(0, 100)
  })),
  updatePosition: (position) => set((state) => ({
    positions: state.positions.map(p =>
      p.id === position.id ? position : p
    )
  })),
}));