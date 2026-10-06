'use client';

import { ReactNode, useContext, createContext, useEffect, useState, useCallback } from 'react';
import { User } from 'firebase/auth';
import { getAuthInstance, onAuthStateChange, getCurrentUser, getFirebaseToken, ShadowOpsProfile, fetchProfile, signOutUser, resendVerificationEmail } from '@/lib/auth';
import { setAuthContextRefreshToken } from '@/lib/api';

interface AuthContextType {
  user: User | null;
  profile: ShadowOpsProfile | null;
  loading: boolean;
  token: string | null;
  isAuthenticated: boolean;
  isEmailVerified: boolean;
  refreshToken: () => Promise<string | null>;
  refreshProfile: () => Promise<void>;
  resendVerification: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<ShadowOpsProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState<string | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);

  const loadProfile = useCallback(async () => {
    if (!user) {
      setProfile(null);
      return;
    }

    setProfileLoading(true);
    try {
      const userProfile = await fetchProfile();
      setProfile(userProfile);
    } catch (error) {
      console.error('Failed to load profile:', error);
      setProfile(null);
    } finally {
      setProfileLoading(false);
    }
  }, [user]);

  const refreshToken = useCallback(async () => {
    const newToken = await getFirebaseToken(true);
    setToken(newToken);
    return newToken;
  }, []);

  const refreshProfile = useCallback(async () => {
    await loadProfile();
  }, [loadProfile]);

  const resendVerification = useCallback(async () => {
    await resendVerificationEmail();
  }, []);

  const logout = useCallback(async () => {
    await signOutUser();
    setUser(null);
    setProfile(null);
    setToken(null);
  }, []);

  useEffect(() => {
    setAuthContextRefreshToken(refreshToken);
  }, [refreshToken]);

  useEffect(() => {
    let mounted = true;

    const unsubscribe = onAuthStateChange(async (user) => {
      if (!mounted) return;

      if (user) {
        const token = await getFirebaseToken();
        setUser(user);
        setToken(token);
      } else {
        setUser(null);
        setProfile(null);
        setToken(null);
      }
      setLoading(false);
    });

    getCurrentUser().then((user) => {
      if (!mounted) return;
      if (user) {
        getFirebaseToken().then((token) => {
          if (mounted) {
            setUser(user);
            setToken(token);
          }
        });
      }
      if (mounted) setLoading(false);
    });

    return () => {
      mounted = false;
      unsubscribe();
    };
  }, []);

  useEffect(() => {
    if (user && !profileLoading) {
      loadProfile();
    }
  }, [user, loadProfile, profileLoading]);

  const isAuthenticated = !!user;
  const isEmailVerified = user?.emailVerified ?? false;

  return (
    <AuthContext.Provider value={{
      user,
      profile,
      loading: loading || profileLoading,
      token,
      isAuthenticated,
      isEmailVerified,
      refreshToken,
      refreshProfile,
      resendVerification,
      logout,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuthContext() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuthContext must be used within an AuthProvider');
  }
  return context;
}