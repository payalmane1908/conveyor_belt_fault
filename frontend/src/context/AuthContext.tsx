/**
 * Prototype Authentication Context
 * 
 * DISCLAIMER: This is a PROTOTYPE DEMO AUTHENTICATION SYSTEM ONLY.
 * It is NOT secure, does not claim enterprise authentication, and uses no hardcoded secrets.
 * Allows switching between roles: Operator, Engineer, Admin.
 */

import React, { createContext, useContext, useState, useEffect } from 'react';

export type UserRole = 'Operator' | 'Engineer' | 'Admin';

export interface User {
  username: string;
  name: string;
  role: UserRole;
  badgeId: string;
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  login: (username: string, role: UserRole) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const STORAGE_KEY = 'sih_conveyor_auth_user';

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) return JSON.parse(saved);
    } catch {
      // Ignore storage errors
    }
    // Default demo session for immediate operator access
    return {
      username: 'op-412',
      name: 'Shift Lead Operator',
      role: 'Operator',
      badgeId: 'BADGE-OP-01'
    };
  });

  useEffect(() => {
    if (user) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, [user]);

  const login = async (username: string, role: UserRole) => {
    // Prototype client-side authentication simulation
    const roleNames: Record<UserRole, string> = {
      Operator: 'Control Room Operator',
      Engineer: 'Reliability & ML Engineer',
      Admin: 'Plant Systems Administrator'
    };
    const newUser: User = {
      username: username || 'operator',
      name: roleNames[role] || 'Operator',
      role,
      badgeId: `BADGE-${role.slice(0, 2).toUpperCase()}-99`
    };
    setUser(newUser);
  };

  const logout = () => {
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, isAuthenticated: !!user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
