import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

import { authApi, setUnauthorizedHandler } from '../api/client';

const AuthContext = createContext(null);

function buildUnauthenticatedState() {
  return {
    status: 'unauthenticated',
    user: null,
  };
}

export function AuthProvider({ children }) {
  const [authState, setAuthState] = useState({
    status: 'loading',
    user: null,
  });
  const [welcomeState, setWelcomeState] = useState({
    visible: false,
    fullName: '',
  });

  useEffect(() => {
    let isActive = true;

    authApi.me()
      .then((user) => {
        if (!isActive) {
          return;
        }
        setAuthState({
          status: 'authenticated',
          user,
        });
      })
      .catch((error) => {
        if (!isActive) {
          return;
        }
        if (error?.status !== 401) {
          console.error('Error restoring auth session:', error);
        }
        setAuthState(buildUnauthenticatedState());
      });

    return () => {
      isActive = false;
    };
  }, []);

  useEffect(() => {
    const handleUnauthorized = () => {
      setWelcomeState({ visible: false, fullName: '' });
      setAuthState(buildUnauthenticatedState());
    };

    setUnauthorizedHandler(handleUnauthorized);
    return () => {
      setUnauthorizedHandler(null);
    };
  }, []);

  const value = useMemo(() => ({
    user: authState.user,
    isLoading: authState.status === 'loading',
    isAuthenticated: authState.status === 'authenticated',
    login: async (credentials) => {
      const user = await authApi.login(credentials);
      setAuthState({
        status: 'authenticated',
        user,
      });
      setWelcomeState({
        visible: true,
        fullName: user.full_name,
      });
      return user;
    },
    logout: async () => {
      try {
        await authApi.logout();
      } catch (error) {
        if (error?.status !== 401) {
          console.error('Error logging out:', error);
        }
      }
      setWelcomeState({ visible: false, fullName: '' });
      setAuthState(buildUnauthenticatedState());
    },
    welcomeState,
    dismissWelcome: () => {
      setWelcomeState({ visible: false, fullName: '' });
    },
  }), [authState, welcomeState]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
