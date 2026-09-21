/**
 * Prototype Authentication Page
 * 
 * Notice: This is a prototype login for demonstration only.
 * Does not claim production or enterprise security.
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import type { UserRole } from '../context/AuthContext';
import { ShieldCheck, Lock, User as UserIcon, Info } from 'lucide-react';
import { config } from '../config';

export const Login: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('op-lead-01');
  const [role, setRole] = useState<UserRole>('Operator');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await login(username, role);
    navigate('/control-room');
  };

  return (
    <div className="min-h-screen w-screen bg-black flex flex-col items-center justify-center p-4 font-sans select-none">
      <div className="w-full max-w-md bg-zinc-950 border border-zinc-800 rounded-lg p-6 shadow-2xl space-y-6">
        {/* Brand Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-lg bg-emerald-950/80 border border-emerald-700/60 text-emerald-400 mb-2">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <h1 className="text-lg font-mono font-bold text-zinc-100 uppercase tracking-wider">
            {config.plantName}
          </h1>
          <p className="text-xs font-mono text-zinc-400">
            Intelligent Conveyor Belt Health Monitoring & Predictive Maintenance System
          </p>
        </div>

        {/* Prototype Disclaimer Banner */}
        <div className="bg-zinc-900/90 border border-zinc-800 rounded p-3 text-xs font-mono text-zinc-400 flex items-start gap-2.5">
          <Info className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
          <div>
            <span className="text-blue-300 font-semibold">Prototype Authentication:</span> This interface provides role-based demonstration access. It does not implement production or enterprise authentication.
          </div>
        </div>

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-mono text-zinc-300 uppercase tracking-wider mb-1.5">
              Operator Identifier / Badge ID
            </label>
            <div className="relative">
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm font-mono text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-emerald-500"
                placeholder="e.g. op-412"
              />
              <UserIcon className="w-4 h-4 text-zinc-500 absolute right-3 top-2.5" />
            </div>
          </div>

          <div>
            <label className="block text-xs font-mono text-zinc-300 uppercase tracking-wider mb-1.5">
              System Operational Role
            </label>
            <div className="grid grid-cols-3 gap-2">
              {(['Operator', 'Engineer', 'Admin'] as UserRole[]).map((r) => (
                <button
                  type="button"
                  key={r}
                  onClick={() => setRole(r)}
                  className={`px-3 py-2 text-xs font-mono rounded border text-center transition-colors cursor-pointer ${
                    role === r
                      ? 'bg-emerald-950/80 border-emerald-600 text-emerald-300 font-bold'
                      : 'bg-zinc-900 border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800'
                  }`}
                >
                  {r}
                </button>
              ))}
            </div>
          </div>

          <div className="pt-2">
            <button
              type="submit"
              className="w-full bg-emerald-600 hover:bg-emerald-500 text-black font-mono font-bold text-xs uppercase tracking-wider py-2.5 rounded transition-colors flex items-center justify-center gap-2 cursor-pointer"
            >
              <Lock className="w-3.5 h-3.5" />
              <span>Access Control Station</span>
            </button>
          </div>
        </form>

        {/* Technical Footer */}
        <div className="text-center text-[10px] font-mono text-zinc-600 pt-2 border-t border-zinc-900">
          Smart India Hackathon • Hardware Track Prototype • Stage 1
        </div>
      </div>
    </div>
  );
};
