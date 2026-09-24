import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api, clearSession, readStoredUser, setSession, setUnauthorizedHandler } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(readStoredUser);
  const [loading, setLoading] = useState(!!localStorage.getItem("cs_token"));
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null);
      if (location.pathname !== "/login") {
        navigate("/login", {
          replace: true,
          state: { notice: "Your session has expired. Please sign in again." },
        });
      }
    });
    return () => setUnauthorizedHandler(null);
  }, [navigate, location.pathname]);

  useEffect(() => {
    const token = localStorage.getItem("cs_token");
    if (!token) {
      setLoading(false);
      return;
    }
    api("/api/auth/me")
      .then((data) => {
        const nextUser = {
          ...data.user,
          first_name: data.user?.first_name || data.profile?.first_name || "",
          last_name: data.user?.last_name || data.profile?.last_name || "",
        };
        setUser(nextUser);
        setSession(token, nextUser);
      })
      .catch(() => {
        clearSession();
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      login: (token, nextUser) => {
        setSession(token, nextUser);
        setUser(nextUser);
      },
      logout: () => {
        clearSession();
        setUser(null);
      },
      refreshUser: async () => {
        const data = await api("/api/auth/me");
        const nextUser = {
          ...data.user,
          first_name: data.user?.first_name || data.profile?.first_name || "",
          last_name: data.user?.last_name || data.profile?.last_name || "",
        };
        setSession(localStorage.getItem("cs_token"), nextUser);
        setUser(nextUser);
        return { ...data, user: nextUser };
      },
    }),
    [user, loading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
