import React, { useState, useEffect } from 'react';
import { supabase } from './supabaseClient';

const cardSt = { background:"#161510", border:"1px solid #2A2820", borderRadius:10, padding:20 };
const labelSt = { display:"block", fontSize:10, letterSpacing:"0.2em", textTransform:"uppercase", color:"#C8BCA4", marginBottom:6, marginTop:14 };
const inputSt = { width:"100%", background:"#0A0908", border:"1px solid #2A2820", borderRadius:6, color:"#E8E2D8", padding:"11px 12px", fontSize:15, outline:"none", fontFamily:"inherit" };

function Section({ title, color="#C8A96E", border="#2A2820", children }) {
  return (
    <div style={{ ...cardSt, border:`1px solid ${border}`, marginBottom:12 }}>
      <div style={{ fontSize:10, letterSpacing:"0.25em", textTransform:"uppercase", color, marginBottom:16 }}>{title}</div>
      {children}
    </div>
  );
}

function Btn({ children, onClick, disabled, variant="gold", style={} }) {
  const bg = disabled ? "#1A1810" : variant==="red" ? "#C87E8A" : variant==="ghost" ? "#1E1C18" : "#C8A96E";
  const col = disabled ? "#7A6A50" : variant==="ghost" ? "#C8A96E" : "#0F0E0C";
  return (
    <button onClick={onClick} disabled={disabled} style={{ width:"100%", marginTop:14, padding:"13px 16px", border:"none", borderRadius:6, fontSize:12, letterSpacing:"0.2em", textTransform:"uppercase", cursor:disabled?"not-allowed":"pointer", background:bg, color:col, fontFamily:"inherit", ...style }}>
      {children}
    </button>
  );
}

function TeamSection({ session, ownerUserId }) {
  const isOwner = !ownerUserId; // if no ownerUserId, this user IS the owner
  const [members, setMembers] = useState([]);
  const [inviteEmail, setInviteEmail] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!isOwner) return;
    loadMembers();
  }, [isOwner]); // eslint-disable-line

  async function loadMembers() {
    const { data } = await supabase.from("team_members")
      .select("member_email, member_id, accepted_at")
      .eq("owner_id", session.user.id)
      .order("invited_at");
    setMembers(data || []);
  }

  async function invite() {
    setMsg(""); setErr("");
    const em = inviteEmail.trim().toLowerCase();
    if (!em || !em.includes("@")) { setErr("Enter a valid email address."); return; }
    if (em === session.user.email) { setErr("That's your own email."); return; }
    setBusy(true);
    try {
      const { error } = await supabase.from("team_members").insert({
        owner_id: session.user.id,
        member_email: em,
      });
      if (error) {
        if (error.code === "23505") setErr("That email is already invited.");
        else throw error;
      } else {
        setMsg(`Invited ${em}. Send them ${window.location.origin} — when they sign up with that email they'll automatically see your data.`);
        setInviteEmail("");
        loadMembers();
      }
    } catch (e) {
      setErr(e.message || "Could not send invite.");
    } finally {
      setBusy(false);
    }
  }

  async function removeMember(memberEmail) {
    if (!window.confirm(`Remove ${memberEmail} from your account? They will lose access immediately.`)) return;
    await supabase.from("team_members").delete()
      .eq("owner_id", session.user.id).eq("member_email", memberEmail);
    loadMembers();
  }

  if (!isOwner) {
    return (
      <Section title="Account Access">
        <div style={{ fontSize:12, color:"#AC9E86", lineHeight:1.7 }}>
          You are logged in as a <span style={{ color:"#C8A96E" }}>team member</span>. You are viewing and editing the account owner's data.
        </div>
      </Section>
    );
  }

  return (
    <Section title="Team Members">
      <div style={{ fontSize:12, color:"#AC9E86", marginBottom:12, lineHeight:1.6 }}>
        Invite someone to share your account — they'll see and edit your same properties, logs, and data.
        For a separate private account, just send them <span style={{ color:"#C8A96E" }}>{window.location.origin}</span> to sign up on their own.
      </div>

      {/* Current members */}
      {members.length > 0 && (
        <div style={{ marginBottom:14 }}>
          <div style={{ fontSize:10, letterSpacing:"0.15em", textTransform:"uppercase", color:"#C8BCA4", marginBottom:8 }}>Current Members</div>
          <div style={{ display:"flex", flexDirection:"column", gap:6 }}>
            {members.map(m => (
              <div key={m.member_email} style={{ display:"flex", alignItems:"center", justifyContent:"space-between", background:"#0A0908", border:"1px solid #2A2820", borderRadius:6, padding:"10px 12px" }}>
                <div>
                  <div style={{ fontSize:13, color:"#E8E2D8" }}>{m.member_email}</div>
                  <div style={{ fontSize:10, color: m.accepted_at ? "#7EB8A4" : "#AC9E86", marginTop:2 }}>
                    {m.accepted_at ? "✓ Active" : "⏳ Pending — hasn't signed up yet"}
                  </div>
                </div>
                <button onClick={() => removeMember(m.member_email)} style={{ background:"none", border:"1px solid #2A2820", color:"#C87E8A", fontSize:10, padding:"5px 9px", borderRadius:3, cursor:"pointer", letterSpacing:"0.1em", textTransform:"uppercase", fontFamily:"inherit" }}>Remove</button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Invite form */}
      <label style={labelSt}>Invite by Email</label>
      <input
        type="email"
        value={inviteEmail}
        onChange={e => setInviteEmail(e.target.value)}
        onKeyDown={e => e.key === "Enter" && invite()}
        style={inputSt}
        placeholder="coworker@example.com"
      />
      {err && <div style={{ fontSize:11, color:"#C87E8A", marginTop:6 }}>{err}</div>}
      {msg && <div style={{ fontSize:11, color:"#7EB8A4", marginTop:8, lineHeight:1.6 }}>{msg}</div>}
      <Btn onClick={invite} disabled={busy || !inviteEmail.trim()}>{busy ? "Inviting…" : "Add to My Account"}</Btn>

      {/* Share link */}
      <div style={{ marginTop:16, paddingTop:14, borderTop:"1px solid #1E1C18" }}>
        <div style={{ fontSize:10, letterSpacing:"0.15em", textTransform:"uppercase", color:"#C8BCA4", marginBottom:8 }}>Or share the site for a separate account</div>
        <div style={{ display:"flex", gap:8, alignItems:"center" }}>
          <div style={{ flex:1, background:"#0A0908", border:"1px solid #2A2820", borderRadius:6, padding:"10px 12px", fontSize:12, color:"#AC9E86", overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{window.location.origin}</div>
          <button onClick={() => { navigator.clipboard.writeText(window.location.origin); setMsg("Link copied!"); setTimeout(()=>setMsg(""),2000); }} style={{ background:"#C8A96E", border:"none", color:"#0F0E0C", fontSize:11, padding:"10px 14px", borderRadius:6, cursor:"pointer", letterSpacing:"0.15em", textTransform:"uppercase", fontFamily:"inherit", flexShrink:0 }}>Copy</button>
        </div>
      </div>
    </Section>
  );
}

export default function AccountView({ session, ownerUserId, onSignOut }) {
  const email = session?.user?.email || "";

  const [newEmail, setNewEmail] = useState("");
  const [emailMsg, setEmailMsg] = useState("");
  const [emailErr, setEmailErr] = useState("");
  const [emailBusy, setEmailBusy] = useState(false);

  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [pwMsg, setPwMsg] = useState("");
  const [pwErr, setPwErr] = useState("");
  const [pwBusy, setPwBusy] = useState(false);

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

        <Section title="Session">
          <div style={{ fontSize:12, color:"#AC9E86" }}>Sign out on this device. Your data stays saved in the cloud.</div>
          <Btn onClick={onSignOut} variant="ghost">Sign Out</Btn>
        </Section>

        <TeamSection session={session} ownerUserId={ownerUserId} />

        <Section title="Change Email">
          <div style={{ fontSize:12, color:"#AC9E86", marginBottom:8 }}>A confirmation link will be sent to the new address.</div>
          <label style={labelSt}>New Email Address</label>
          <input type="email" value={newEmail} onChange={e=>setNewEmail(e.target.value)} style={inputSt} placeholder={email} />
          {emailErr && <div style={{ fontSize:11, color:"#C87E8A", marginTop:6 }}>{emailErr}</div>}
          {emailMsg && <div style={{ fontSize:11, color:"#7EB8A4", marginTop:6 }}>{emailMsg}</div>}
          <Btn onClick={changeEmail} disabled={emailBusy || !newEmail.trim()}>{emailBusy ? "Sending…" : "Update Email"}</Btn>
        </Section>

        <Section title="Change Password">
          <label style={labelSt}>New Password</label>
          <input type="password" value={newPw} onChange={e=>setNewPw(e.target.value)} style={inputSt} placeholder="At least 6 characters" />
          <label style={labelSt}>Confirm New Password</label>
          <input type="password" value={confirmPw} onChange={e=>setConfirmPw(e.target.value)} style={inputSt} placeholder="Repeat password" />
          {pwErr && <div style={{ fontSize:11, color:"#C87E8A", marginTop:6 }}>{pwErr}</div>}
          {pwMsg && <div style={{ fontSize:11, color:"#7EB8A4", marginTop:6 }}>{pwMsg}</div>}
          <Btn onClick={changePassword} disabled={pwBusy || !newPw || !confirmPw}>{pwBusy ? "Updating…" : "Update Password"}</Btn>
        </Section>

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
