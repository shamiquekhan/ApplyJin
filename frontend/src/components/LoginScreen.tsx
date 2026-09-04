import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { ArrowLeft, Loader2 } from "lucide-react";
import { API_BASE } from "../lib/apiBase";
import { fetchMe } from "../lib/session";
import { navigate } from "../lib/router";

/**
 * Sign-in gate for the Console. When auth is disabled on the backend
 * (local / zero-config mode) it lets the user straight through.
 */
export function LoginScreen() {
  const [checking, setChecking] = useState(true);
  const [error, setError] = useState("");
  const reduce = useReducedMotion();

  useEffect(() => {
    fetchMe()
      .then((me) => {
        if (!me.auth_enabled || me.user) {
          navigate("/dashboard"); // open instance, or already signed in
        } else {
          setChecking(false);
        }
      })
      .catch(() => setChecking(false));
  }, []);

  if (checking) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <Loader2 className="w-6 h-6 text-primary animate-spin" aria-label="Checking session" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-black p-4 md:p-6 flex items-center justify-center">
      <motion.div
        className="bg-[#101010] rounded-2xl border border-primary/10 p-8 md:p-12 max-w-md w-full text-center"
        initial={reduce ? undefined : { opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <button
          onClick={() => navigate("/")}
          className="flex items-center gap-2 text-primary/60 hover:text-primary text-sm mb-8 mx-auto"
        >
          <ArrowLeft className="w-4 h-4" aria-hidden="true" /> ApplyJin
        </button>

        <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-700 flex items-center justify-center text-white font-bold text-2xl mx-auto mb-6">
          A
        </div>
        <h1 className="text-2xl font-medium mb-2" style={{ color: "#E1E0CC" }}>
          Sign in to the Console
        </h1>
        <p className="text-primary/50 text-sm mb-8">
          Your resumes, the master CV database, and tailored applications live
          behind this door.
        </p>

        {error && (
          <p className="text-red-400 text-xs mb-4" role="alert">{error}</p>
        )}

        {/* Google's own branding guidelines for the button */}
        <a
          href={`${API_BASE}/api/auth/google`}
          className="flex items-center justify-center gap-3 w-full bg-white hover:bg-gray-50 text-gray-800 rounded-full py-3 px-4 text-sm font-medium transition-colors"
        >
          <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
            <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
            <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
            <path fill="#FBBC05" d="M10.53 28.59A14.5 14.5 0 0 1 9.5 24c0-1.6.27-3.15.76-4.59l-7.98-6.19A23.94 23.94 0 0 0 0 24c0 3.88.93 7.54 2.56 10.78l7.97-6.19z"/>
            <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.46-9.91l-7.97 6.19C6.51 42.62 14.62 48 24 48z"/>
          </svg>
          Continue with Google
        </a>

        <p className="text-primary/30 text-[11px] mt-6">
          We only read your name and email from Google — nothing else.
        </p>
      </motion.div>
    </div>
  );
}
