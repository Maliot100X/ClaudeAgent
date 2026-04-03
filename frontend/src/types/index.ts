export interface Signal {
  id: string;
  symbol: string;
  type: 'BUY' | 'SELL' | 'HOLD';
  strength: number;
  price: number;
  reasoning: string;
  timestamp: string;
}

export interface Position {
  id: string;
  symbol: string;
  side: 'LONG' | 'SHORT';
  entryPrice: number;
  currentPrice: number;
  quantity: number;
  unrealizedPnl: number;
  unrealizedPnlPct: number;
  stopLoss?: number;
  takeProfit?: number;
}

export interface Agent {
  id: string;
  name: string;
  type: string;
  isActive: boolean;
  lastAction: string;
  skillsCount: number;
}

export interface PerformanceMetrics {
  totalEquity: number;
  totalReturn: number;
  totalReturnPct: number;
  totalTrades: number;
  winningTrades: number;
  losingTrades: number;
  winRate: number;
}

export interface Strategy {
  id: string;
  name: string;
  type: string;
  symbols: string[];
  isActive: boolean;
  signalsGenerated: number;
}