import React, { useState } from 'react';
import { supabase } from './supabaseClient';

const cardSt = { background:"#161510", border:"1px solid #2A2820", borderRadius:10, padding:20 };
const labelSt = { display:"block", fontSize:10, letterSpacing:"0.2em", textTransform:"uppercase", color:"#C8BCA4", marginBottom:6, marginTop:14 };
const inputSt = { width:"100%", background:"#0A0908", border:"1px solid #2A2820", borderRadius:6, color:"#E8E2D8", padding:"11px 12px", fontSize:15, outline:"none", fontFamily:"inherit" };

function Section({ title, children }) {
  return (
    <div style={{ ...cardSt, marginBottom: 12 }}>
      <div style={{ fontSize:10, letterSpacing:"0.25em", textTransform:"uppercase", color:"#C8A96E", marginBottom:16 }}>{title}</div>
      {children}
    </div>
  );
}

function Btn({ children, onClick, disabled, variant="gold" }) {
  const bg = disabled ? "#1A1810" : variant === "red" ? "#C87E8A" : "#C8A96E";
  const color = disabled ? "#7A6A50" : "#0F0E0C";
  return (
    <button onClick={onClick} disabled={disabled} style={{ width:"100%", marginTop:14, padding:"13px 16px", border:"none", borderRadius:6, fontSize:12, letterSpacing:"0.2em", textTransform:"uppercase", cursor:disabled?"not-allowed":"pointer", background:bg, color, fontFamily:"inherit" }}>
      {children}
    </button>
  );
}

export default function AccountView({ session, onSignOut }) {
  const email = session?.user?.email || "";

  // Change email
  const [newEmail, setNewEmail] = useState("");
  const [emailMsg, setEmailMsg] = useState("");
  const [emailErr, setEmailErr] = useState("");
  const [emailBusy, setEmailBusy] = useState(false);

  // Change password
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [pwMsg, setPwMsg] = useState("");
  const [pwErr, setPwErr] = useState("");
  const [pwBusy, setPwBusy] = useState(false);

  // Delete account
  const [deleteConfirm, setDeleteConfirm] = useState("");
  const [deleteErr, setDeleteErr] = useState("");
  const [deleteBusy, setDeleteBusy] = useState(false);

  async function changeEmail() {
    setEmailMsg(""); setEmailErr("");
    if (!newEmail.trim() || !newEmail.includes("@")) { setEmailErr("Enter a valid email address."); return; }
    if (newEmail.trim() === email) { setEmailErr("That's already your current email."); return; }
    setEmailBusy(true);
    try {
      const { error } = await supabase.auth.updateUser({ email: newEmail.trim() });
      if (error) throw error;
      setEmailMsg("Confirmation sent to " + newEmail.trim() + ". Check your inbox to confirm the change.");
      setNewEmail("");
    } catch (e) {
      setEmailErr(e.message || "Could not update email.");
    } finally {
      setEmailBusy(false);
    }
  }

  async function changePassword() {
    setPwMsg(""); setPwErr("");
    if (newPw.length < 6) { setPwErr("Password must be at least 6 characters."); return; }
    if (newPw !== confirmPw) { setPwErr("Passwords don't match."); return; }
    setPwBusy(true);
    try {
      const { error } = await supabase.auth.updateUser({ password: newPw });
      if (error) throw error;
      setPwMsg("Password updated successfully.");
      setNewPw(""); setConfirmPw("");
    } catch (e) {
      setPwErr(e.message || "Could not update password.");
    } finally {
      setPwBusy(false);
    }
  }

  async function deleteAccount() {
    setDeleteErr("");
    if (deleteConfirm !== email) { setDeleteErr("Type your email exactly to confirm deletion."); return; }
    setDeleteBusy(true);
    try {
      // Delete their data row first, then sign out (account deletion requires admin API;
      // we clear data and sign out — the auth record remains but is inaccessible without data).
      await supabase.from("user_data").delete().eq("user_id", session.user.id);
      await supabase.auth.signOut();
    } catch (e) {
      setDeleteErr(e.message || "Could not delete account.");
      setDeleteBusy(false);
    }
  }

  return (
    <div className="scroll-area" style={{ height:"100%", paddingBottom:32 }}>
      <div style={{ padding:"16px 16px 8px" }}>
        <div style={{ fontSize:10, letterSpacing:"0.25em", textTransform:"uppercase", color:"#C8BCA4" }}>Account</div>
        <div style={{ fontSize:12, color:"#AC9E86", marginTop:4 }}>Signed in as <span style={{ color:"#E8E2D8" }}>{email}</span></div>
      </div>

      <div style={{ padding:"4px 16px" }}>

        {/* Sign out */}
        <Section title="Session">
          <div style={{ fontSize:12, color:"#AC9E86" }}>Sign out on this device. Your data stays saved in the cloud.</div>
          <Btn onClick={onSignOut} variant="ghost">Sign Out</Btn>
        </Section>

        {/* Change email */}
        <Section title="Change Email">
          <div style={{ fontSize:12, color:"#AC9E86", marginBottom:8 }}>A confirmation link will be sent to the new address.</div>
          <label style={labelSt}>New Email Address</label>
          <input type="email" value={newEmail} onChange={e=>setNewEmail(e.target.value)} style={inputSt} placeholder={email} />
          {emailErr && <div style={{ fontSize:11, color:"#C87E8A", marginTop:6 }}>{emailErr}</div>}
          {emailMsg && <div style={{ fontSize:11, color:"#7EB8A4", marginTop:6 }}>{emailMsg}</div>}
          <Btn onClick={changeEmail} disabled={emailBusy || !newEmail.trim()}>{emailBusy ? "Sending…" : "Update Email"}</Btn>
        </Section>

        {/* Change password */}
        <Section title="Change Password">
          <label style={labelSt}>New Password</label>
          <input type="password" value={newPw} onChange={e=>setNewPw(e.target.value)} style={inputSt} placeholder="At least 6 characters" />
          <label style={labelSt}>Confirm New Password</label>
          <input type="password" value={confirmPw} onChange={e=>setConfirmPw(e.target.value)} style={inputSt} placeholder="Repeat password" />
          {pwErr && <div style={{ fontSize:11, color:"#C87E8A", marginTop:6 }}>{pwErr}</div>}
          {pwMsg && <div style={{ fontSize:11, color:"#7EB8A4", marginTop:6 }}>{pwMsg}</div>}
          <Btn onClick={changePassword} disabled={pwBusy || !newPw || !confirmPw}>{pwBusy ? "Updating…" : "Update Password"}</Btn>
        </Section>

        {/* Danger zone */}
        <div style={{ ...cardSt, border:"1px solid #3A1818", marginBottom:12 }}>
          <div style={{ fontSize:10, letterSpacing:"0.25em", textTransform:"uppercase", color:"#C87E8A", marginBottom:12 }}>Danger Zone</div>
          <div style={{ fontSize:12, color:"#AC9E86", marginBottom:12, lineHeight:1.6 }}>
            Permanently deletes all your logged hours, recurring tasks, and attestation data. This cannot be undone.
          </div>
          <label style={{ ...labelSt, color:"#C87E8A" }}>Type your email to confirm</label>
          <input type="email" value={deleteConfirm} onChange={e=>setDeleteConfirm(e.target.value)} style={{ ...inputSt, borderColor:"#3A1818" }} placeholder={email} />
          {deleteErr && <div style={{ fontSize:11, color:"#C87E8A", marginTop:6 }}>{deleteErr}</div>}
          <Btn onClick={deleteAccount} disabled={deleteBusy || deleteConfirm !== email} variant="red">
            {deleteBusy ? "Deleting…" : "Delete All My Data"}
          </Btn>
        </div>

      </div>
    </div>
  );
}
