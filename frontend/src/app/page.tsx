'use client';

import { motion } from 'framer-motion';
import { useState, useEffect } from 'react';
import { Activity, TrendingUp, Bot, Signal, Wallet, Settings, Bell, Menu, X } from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

// Utility for tailwind class merging
function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// Simple card component
function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("glass rounded-xl p-6", className)}>
      {children}
    </div>
  );
}

// Stat card component
function StatCard({ title, value, change, icon: Icon }: { title: string; value: string; change?: string; icon: any }) {
  const isPositive = change?.startsWith('+');
  return (
    <Card className="hover:scale-[1.02] transition-transform duration-300">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-muted-foreground text-sm">{title}</p>
          <h3 className="text-2xl font-bold mt-1">{value}</h3>
          {change && (
            <p className={cn("text-sm mt-1", isPositive ? "text-green-400" : "text-red-400")}>
              {change}
            </p>
          )}
        </div>
        <div className="p-3 bg-primary/10 rounded-lg">
          <Icon className="w-5 h-5 text-primary" />
        </div>
      </div>
    </Card>
  );
}

// Mock data for the dashboard
const mockSignals = [
  { id: 1, symbol: 'BTC', type: 'BUY', price: 67234.50, strength: 4, time: '2 min ago' },
  { id: 2, symbol: 'ETH', type: 'SELL', price: 3456.78, strength: 3, time: '5 min ago' },
  { id: 3, symbol: 'SOL', type: 'BUY', price: 145.23, strength: 5, time: '12 min ago' },
];

const mockPositions = [
  { symbol: 'BTC', side: 'LONG', entry: 65000, current: 67234, pnl: '+3.44%', size: '0.15 BTC' },
  { symbol: 'ETH', side: 'LONG', entry: 3200, current: 3456, pnl: '+8.00%', size: '2.5 ETH' },
];

// Simple recharts-style chart component
function SimpleChart() {
  const data = [65, 68, 70, 72, 71, 74, 76, 78, 80, 79, 82, 85];
  const max = Math.max(...data);
  const min = Math.min(...data);

  return (
    <div className="h-48 w-full flex items-end gap-1">
      {data.map((value, i) => {
        const height = ((value - min) / (max - min)) * 100;
        return (
          <motion.div
            key={i}
            initial={{ height: 0 }}
            animate={{ height: `${height}%` }}
            transition={{ delay: i * 0.05, duration: 0.5 }}
            className="flex-1 bg-gradient-to-t from-primary/50 to-primary rounded-t-sm hover:from-primary/70 hover:to-primary/90 transition-colors"
          />
        );
      })}
    </div>
  );
}

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState('overview');
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return null;

  const navItems = [
    { id: 'overview', label: 'Overview', icon: Activity },
    { id: 'agents', label: 'Agents', icon: Bot },
    { id: 'signals', label: 'Signals', icon: Signal },
    { id: 'positions', label: 'Positions', icon: Wallet },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  return (
    <div className="min-h-screen bg-background grid-pattern">
      {/* Sidebar */}
      <aside className={cn(
        "fixed top-0 left-0 z-50 h-full w-64 glass border-r border-border transition-transform duration-300",
        isMobileMenuOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
      )}>
        <div className="p-6 flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary to-purple-600 flex items-center justify-center">
            <Bot className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="font-bold text-lg">AI Agent</h1>
            <p className="text-xs text-muted-foreground">Trading Platform</p>
          </div>
        </div>

        <nav className="px-4 py-4 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={cn(
                  "w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all",
                  isActive
                    ? "bg-primary/10 text-primary border border-primary/20"
                    : "text-muted-foreground hover:text-foreground hover:bg-white/5"
                )}
              >
                <Icon className="w-5 h-5" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="absolute bottom-0 left-0 right-0 p-4">
          <Card className="!p-4">
            <div className="flex items-center gap-3">
              <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              <div className="flex-1">
                <p className="text-sm font-medium">System Online</p>
                <p className="text-xs text-muted-foreground">All agents running</p>
              </div>
            </div>
          </Card>
        </div>
      </aside>

      {/* Main content */}
      <main className="lg:ml-64 min-h-screen">
        {/* Header */}
        <header className="sticky top-0 z-40 glass border-b border-border">
          <div className="flex items-center justify-between px-6 py-4">
            <div className="flex items-center gap-4">
              <button
                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                className="lg:hidden p-2 hover:bg-white/5 rounded-lg"
              >
                {isMobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
              <h2 className="text-xl font-semibold capitalize">{activeTab}</h2>
            </div>
            <div className="flex items-center gap-4">
              <button className="relative p-2 hover:bg-white/5 rounded-lg">
                <Bell className="w-5 h-5" />
                <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full" />
              </button>
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary to-purple-600" />
            </div>
          </div>
        </header>

        {/* Dashboard content */}
        <div className="p-6 space-y-6">
          {/* Stats row */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              title="Portfolio Value"
              value="$105,120.50"
              change="+5.12%"
              icon={Wallet}
            />
            <StatCard
              title="Active Signals"
              value="12"
              change="+3 today"
              icon={Signal}
            />
            <StatCard
              title="Win Rate"
              value="67.3%"
              change="+2.1%"
              icon={TrendingUp}
            />
            <StatCard
              title="Active Agents"
              value="4"
              change="All healthy"
              icon={Bot}
            />
          </div>

          {/* Charts and signals */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Main chart */}
            <Card className="lg:col-span-2">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold">Portfolio Performance</h3>
                <div className="flex gap-2">
                  {['1H', '1D', '1W', '1M'].map((tf) => (
                    <button
                      key={tf}
                      className="px-3 py-1 text-xs rounded bg-white/5 hover:bg-white/10 transition-colors"
                    >
                      {tf}
                    </button>
                  ))}
                </div>
              </div>
              <SimpleChart />
            </Card>

            {/* Recent signals */}
            <Card>
              <h3 className="font-semibold mb-4">Recent Signals</h3>
              <div className="space-y-3">
                {mockSignals.map((signal) => (
                  <motion.div
                    key={signal.id}
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="flex items-center justify-between p-3 bg-white/5 rounded-lg"
                  >
                    <div className="flex items-center gap-3">
                      <div className={cn(
                        "w-8 h-8 rounded flex items-center justify-center text-xs font-bold",
                        signal.type === 'BUY' ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"
                      )}>
                        {signal.type}
                      </div>
                      <div>
                        <p className="font-medium">{signal.symbol}</p>
                        <p className="text-xs text-muted-foreground">{signal.time}</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="font-medium">${signal.price.toLocaleString()}</p>
                      <p className="text-xs text-muted-foreground">{'⭐'.repeat(signal.strength)}</p>
                    </div>
                  </motion.div>
                ))}
              </div>
            </Card>
          </div>

          {/* Positions table */}
          <Card>
            <h3 className="font-semibold mb-4">Open Positions</h3>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-sm text-muted-foreground border-b border-border">
                    <th className="pb-3 font-medium">Symbol</th>
                    <th className="pb-3 font-medium">Side</th>
                    <th className="pb-3 font-medium">Entry Price</th>
                    <th className="pb-3 font-medium">Current</th>
                    <th className="pb-3 font-medium">Size</th>
                    <th className="pb-3 font-medium">P&L</th>
                  </tr>
                </thead>
                <tbody>
                  {mockPositions.map((pos, i) => (
                    <motion.tr
                      key={pos.symbol}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: i * 0.1 }}
                      className="border-b border-border/50 last:border-0"
                    >
                      <td className="py-4 font-medium">{pos.symbol}</td>
                      <td className="py-4">
                        <span className={cn(
                          "px-2 py-1 rounded text-xs font-medium",
                          pos.side === 'LONG' ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"
                        )}>
                          {pos.side}
                        </span>
                      </td>
                      <td className="py-4 text-muted-foreground">${pos.entry.toLocaleString()}</td>
                      <td className="py-4">${pos.current.toLocaleString()}</td>
                      <td className="py-4 text-muted-foreground">{pos.size}</td>
                      <td className="py-4">
                        <span className={cn(
                          pos.pnl.startsWith('+') ? "text-green-400" : "text-red-400"
                        )}>
                          {pos.pnl}
                        </span>
                      </td>
                    </motion.tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Footer */}
          <footer className="text-center text-sm text-muted-foreground py-4">
            <p>AI Agent Platform v1.0.0 • Paper Trading Only • {new Date().getFullYear()}</p>
          </footer>
        </div>
      </main>

      {/* Mobile overlay */}
      {isMobileMenuOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setIsMobileMenuOpen(false)}
        />
      )}
    </div>
  );
}