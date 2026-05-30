import React, { useState } from 'react';
import { supabase } from './supabaseClient';

const wrap = { minHeight:"100vh", background:"#0F0E0C", color:"#E8E2D8", display:"flex", alignItems:"center", justifyContent:"center", padding:"24px", fontFamily:"Georgia, 'Times New Roman', serif" };
const card = { width:"100%", maxWidth:380, background:"#161510", border:"1px solid #2A2820", borderRadius:12, padding:28 };
const labelSt = { display:"block", fontSize:10, letterSpacing:"0.2em", textTransform:"uppercase", color:"#C8BCA4", marginBottom:6, marginTop:16 };
const inputSt = { width:"100%", background:"#0A0908", border:"1px solid #2A2820", borderRadius:6, color:"#E8E2D8", padding:"12px", fontSize:15, outline:"none", fontFamily:"inherit" };

export default function Auth() {
  const [mode, setMode] = useState("signin"); // signin | signup
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  async function submit(e) {
    e?.preventDefault();
    setErr(""); setMsg("");
    if (!email.trim() || password.length < 6) {
      setErr("Enter an email and a password of at least 6 characters.");
      return;
    }
    setBusy(true);
    try {
      if (mode === "signup") {
        const { data, error } = await supabase.auth.signUp({ email: email.trim(), password });
        if (error) throw error;
        if (data.session) {
          // Email confirmation disabled → signed in immediately. App will pick up the session.
        } else {
          setMsg("Account created. Check your email to confirm, then sign in.");
          setMode("signin");
        }
      } else {
        const { error } = await supabase.auth.signInWithPassword({ email: email.trim(), password });
        if (error) throw error;
        // Signed in → App's auth listener takes over.
      }
    } catch (e2) {
      setErr(e2.message || "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  async function resetPassword() {
    setErr(""); setMsg("");
    if (!email.trim()) { setErr("Enter your email first, then tap reset."); return; }
    setBusy(true);
    try {
      // Always send people back to the deployed app, never to a dev URL like
      // localhost:3000 (which is what window.location.origin would be if the
      // reset was requested from a local build).
      const SITE_URL = "https://rep-pwa.vercel.app";
      const { error } = await supabase.auth.resetPasswordForEmail(email.trim(), { redirectTo: SITE_URL });
      if (error) throw error;
      setMsg("Password reset link sent — check your email.");
    } catch (e2) {
      setErr(e2.message || "Could not send reset email.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={wrap}>
      <form style={card} onSubmit={submit}>
        <div style={{ fontSize:9, letterSpacing:"0.25em", textTransform:"uppercase", color:"#AC9E86", marginBottom:2 }}>DFM Capital LLC</div>
        <div style={{ fontSize:22, color:"#E8E2D8", lineHeight:1.1 }}>REP Hour Log</div>
        <div style={{ fontSize:12, color:"#AC9E86", marginTop:6 }}>
          {mode === "signin" ? "Sign in to your synced log." : "Create an account — your hours sync across all devices."}
        </div>

        <label style={labelSt}>Email</label>
        <input type="email" autoComplete="email" value={email} onChange={e=>setEmail(e.target.value)} style={inputSt} placeholder="you@example.com" />

        <label style={labelSt}>Password</label>
        <input type="password" autoComplete={mode==="signup"?"new-password":"current-password"} value={password} onChange={e=>setPassword(e.target.value)} style={inputSt} placeholder="••••••••" />

        {err && <div style={{ fontSize:12, color:"#C87E8A", marginTop:12 }}>{err}</div>}
        {msg && <div style={{ fontSize:12, color:"#7EB8A4", marginTop:12 }}>{msg}</div>}

        <button type="submit" disabled={busy} style={{ width:"100%", marginTop:20, padding:"13px", border:"none", borderRadius:6, fontSize:12, letterSpacing:"0.2em", textTransform:"uppercase", cursor:busy?"not-allowed":"pointer", background:busy?"#1A1810":"#C8A96E", color:busy?"#7A6A50":"#0F0E0C", fontFamily:"inherit" }}>
          {busy ? "…" : (mode === "signin" ? "Sign In" : "Create Account")}
        </button>

        <div style={{ display:"flex", justifyContent:"space-between", marginTop:16 }}>
          <button type="button" onClick={()=>{ setMode(mode==="signin"?"signup":"signin"); setErr(""); setMsg(""); }} style={{ background:"none", border:"none", color:"#C8A96E", fontSize:11, cursor:"pointer", letterSpacing:"0.1em", fontFamily:"inherit" }}>
            {mode === "signin" ? "Need an account? Sign up" : "Have an account? Sign in"}
          </button>
          {mode === "signin" && (
            <button type="button" onClick={resetPassword} style={{ background:"none", border:"none", color:"#AC9E86", fontSize:11, cursor:"pointer", fontFamily:"inherit" }}>
              Reset password
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
