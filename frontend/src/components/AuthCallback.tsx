import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { setToken } from "../lib/session";
import { navigate } from "../lib/router";

/**
 * OAuth landing: the backend redirects here with the JWT in the URL
 * fragment (#token=...) — fragments never reach server logs or
 * referrers. Store it and go to the Console.
 */
export function AuthCallback() {
  const [error, setError] = useState("");

  useEffect(() => {
    const hash = window.location.hash.replace(/^#/, "");
    const params = new URLSearchParams(hash);
    const token = params.get("token");
    const oauthError = params.get("error");
    if (token) {
      setToken(token);
      navigate("/dashboard");
    } else if (oauthError) {
      setError(oauthError);
    } else {
      setError("no_token");
    }
  }, []);

  if (error) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center p-6">
        <div className="bg-[#101010] border border-primary/10 rounded-2xl p-8 max-w-md text-center">
          <p className="text-red-400 text-sm mb-4">
            Sign-in didn't complete ({error}).
          </p>
          <button
            onClick={() => navigate("/dashboard")}
            className="text-primary text-sm underline"
          >
            Back to the Console
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-black flex items-center justify-center">
      <div className="flex items-center gap-3 text-primary/70 text-sm">
        <Loader2 className="w-5 h-5 animate-spin" aria-hidden="true" />
        Signing you in…
      </div>
    </div>
  );
}
