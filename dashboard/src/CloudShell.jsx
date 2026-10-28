import React, { useEffect, useState } from "react";
import { initializeApp } from "firebase/app";
import {
  getAuth,
  GoogleAuthProvider,
  onAuthStateChanged,
  signInWithPopup,
  signOut,
} from "firebase/auth";
import Platform from "./Platform";
export default function CloudShell() {
  const [auth, setAuth] = useState(null),
    [user, setUser] = useState(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [account, setAccount] = useState(null);
  useEffect(() => {
    if (
      !import.meta.env.VITE_FIREBASE_API_KEY ||
      !import.meta.env.VITE_FIREBASE_PROJECT_ID
    ) {
      setLoading(false);
      setError(
        "Production identity is not configured. Set the Firebase public application configuration when building this dashboard.",
      );
      return;
    }
    const app = initializeApp({
      apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
      authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
      projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
    });
    const a = getAuth(app);
    setAuth(a);
    return onAuthStateChanged(a, (u) => {
      setUser(u);
      setLoading(false);
    });
  }, []);
  const api = async (path, body) => {
    if (!user) throw Error("Sign in to Hiyo");
    const token = await user.getIdToken();
    const r = await fetch(path.startsWith("/api/") ? path : "/api" + path, {
      method: body === undefined ? "GET" : "POST",
      headers: {
        Authorization: "Bearer " + token,
        "Content-Type": "application/json",
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const data = await r.json();
    if (!r.ok)
      throw Error(
        typeof data.detail === "string" ? data.detail : "Request failed",
      );
    return data;
  };
  useEffect(() => {
    if (user)
      api("/account")
        .then(setAccount)
        .catch((e) => setError(e.message));
  }, [user]);
  const enroll = async () => {
    try {
      const ticket = await api("/device-enrollment", {});
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(ticket)], { type: "application/json" }),
      );
      const a = document.createElement("a");
      a.href = url;
      a.download = "hiyo-enrollment.json";
      a.click();
      URL.revokeObjectURL(url);
      setError(
        "Enrollment file downloaded. It expires in 15 minutes. Use scripts/install-device.ps1 on your computer; keep the file private.",
      );
    } catch (e) {
      setError(e.message);
    }
  };
  if (!user)
    return (
      <div className="login">
        <div className="login-mark">
          h<span>·</span>
        </div>
        <p className="eyebrow">HIYO / AI AUTOMATION OS</p>
        <h1>
          Your business.
          <br />
          Intelligently connected.
        </h1>
        <p>Industry-aware automation. Local computing. One secure dashboard.</p>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <button
          className="primary"
          disabled={!auth || loading}
          onClick={() =>
            signInWithPopup(auth, new GoogleAuthProvider()).catch((e) =>
              setError(e.message),
            )
          }
        >
          {loading ? "Loading identity…" : "Continue with Google"}
        </button>
      </div>
    );
  return (
    <>
      <div className="cloud-account-bar">
        <b>{user.email || "Hiyo account"}</b>
        <span>
          {account
            ? `${account.jobs_used}/${account.jobs_limit} jobs · $${account.estimated_reserved_usd.toFixed(3)} estimated allocation · $1/mo target`
            : "Local-first cloud coordination"}
        </span>
        <button onClick={enroll}>Enroll computer</button>
        {account?.devices?.map((d) => (
          <span key={d.id}>
            {d.name}: {d.active ? "enrolled" : "revoked"}
          </span>
        ))}
      </div>
      {error && (
        <div className="cloud-account-message" role="status">
          {error}
          <button onClick={() => setError("")}>×</button>
        </div>
      )}
      <Platform
        cloud={true}
        refreshInterval={60000}
        api={api}
        preview={false}
        onEngineering={() =>
          setError(
            "The engineering module runs on your authorized computer. Install the local Hiyo application.",
          )
        }
        onLogout={() => signOut(auth)}
      />
    </>
  );
}
