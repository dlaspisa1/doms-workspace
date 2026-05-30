import React, { useState, useEffect, useRef } from 'react';
import { supabase, hasSupabase } from './supabaseClient';
import Auth from './Auth';
import AccountView from './AccountView';

// ─── Data ───────────────────────────────────────────────────────────────────

const CATEGORIES = [
  { id:"acquisition", label:"Acquisition & Disposition", icon:"🏗", color:"#C8A96E",
    activities:["Property search & analysis","Due diligence review","Offer preparation & negotiation","Contract review & execution","Closing coordination","Title & escrow communication","Broker/agent meetings","Disposition / sale preparation"] },
  { id:"development", label:"Development & Construction", icon:"🔨", color:"#7EB8A4",
    activities:["Contractor sourcing & bidding","Construction oversight / site visits","Permit coordination","Architectural / design review","Renovation project management","Zoning & entitlement research"] },
  { id:"management", label:"Property Management", icon:"🏠", color:"#8FA8C8",
    activities:["Tenant communication","Lease negotiation & execution","Rent collection / Section 8 coordination","Maintenance coordination","Vendor management","Move-in / move-out inspections","Eviction proceedings","Property walk-throughs"] },
  { id:"leasing", label:"Rental & Leasing", icon:"🔑", color:"#C87E8A",
    activities:["Listing preparation & marketing","Showing units to prospective tenants","Tenant screening & background checks","Lease drafting & review","Vacancy analysis"] },
  { id:"finance", label:"Finance & Accounting", icon:"📊", color:"#A08CC8",
    activities:["Bookkeeping & expense tracking","Loan / financing research","Lender communication","Insurance review & coordination","Tax planning & CPA meetings","Financial statement review","Investor reporting"] },
  { id:"legal", label:"Legal & Compliance", icon:"⚖️", color:"#C8A07E",
    activities:["Attorney communication","Contract drafting / review","Landlord-tenant law research","Entity / LLC administration","FIRPTA / tax compliance","Dispute resolution"] },
  { id:"education", label:"Education & Professional Development", icon:"📚", color:"#7EC8B4",
    activities:["Real estate market research","Industry courses / webinars","Networking with professionals","Reading trade publications"] },
];

const DEFAULT_PROPERTIES = [
  "433–439 W. Osborn Rd, Phoenix",
  "2702 E. Juniper (sold duplex)",
  "14515 E Prairie Dog Trail, Fountain Hills",
  "General / Portfolio-wide",
  "Other",
];

const makeEmptyForm = () => ({editingId:null,category:"",activities:[],properties:[],description:"",notes:"",date:todayStr(),endDate:"",mh:"",mm:""});
const makeEmptyRf = () => ({category:"",activities:[],properties:[],description:"",notes:"",hours:"",minutes:"",startDate:todayStr(),endDate:"",freq:"weekly"});

// ─── Helpers ─────────────────────────────────────────────────────────────────

function fmtDur(ms){const s=Math.floor(ms/1000),h=Math.floor(s/3600),m=Math.floor((s%3600)/60),sec=s%60;return `${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}:${String(sec).padStart(2,"0")}`;}
function fmtHrs(ms){return (ms/3600000).toFixed(2);}
function todayStr(){return new Date().toISOString().split("T")[0];}
// Display name: a name set on the account if present, otherwise a Title-Cased
// version of the email's local part (e.g. "dominick" -> "Dominick").
function displayName(user){
  if(!user)return "";
  const meta=user.user_metadata||{};
  const name=(meta.full_name||meta.name||"").trim();
  if(name)return name;
  const local=(user.email||"").split("@")[0].replace(/[._-]+/g," ").trim();
  return local.split(" ").filter(Boolean).map(w=>w[0].toUpperCase()+w.slice(1)).join(" ");
}
function weekKey(dateStr){const d=new Date(dateStr+"T00:00:00"),j=new Date(d.getFullYear(),0,1);return `${d.getFullYear()}-W${String(Math.ceil(((d-j)/86400000+j.getDay()+1)/7)).padStart(2,"0")}`;}
function weeksSince(start,end){const dates=[],s=new Date(start+"T00:00:00"),cap=end?new Date(end+"T00:00:00"):new Date(todayStr()+"T00:00:00");let c=new Date(s);while(c<=cap){dates.push(c.toISOString().split("T")[0]);c.setDate(c.getDate()+7);}return dates;}
// Monthly cadence: one date per month from start through end (or today),
// pinned to the start date's day-of-month. Used by monthly recurring tasks.
function monthsSince(start,end){const dates=[],s=new Date(start+"T00:00:00"),cap=end?new Date(end+"T00:00:00"):new Date(todayStr()+"T00:00:00");const day=s.getDate();let c=new Date(s.getFullYear(),s.getMonth(),day);while(c<=cap){dates.push(c.toISOString().split("T")[0]);c=new Date(c.getFullYear(),c.getMonth()+1,day);}return dates;}
// Pick the right occurrence generator for a task based on its frequency.
function occurrences(task){return (task.freq==="monthly"?monthsSince:weeksSince)(task.startDate,task.endDate);}
function fmtDate(str){if(!str)return "";const[y,m,d]=str.split("-");return `${m}/${d}/${y}`;}
function fmtRange(start,end){if(!end||end===start)return fmtDate(start);return `${fmtDate(start)} – ${fmtDate(end)}`;}

const LS={
  get:(k,d)=>{try{const v=localStorage.getItem(k);return v?JSON.parse(v):d;}catch{return d;}},
  set:(k,v)=>{try{localStorage.setItem(k,JSON.stringify(v));}catch{}}
};

// ─── Shared UI primitives ─────────────────────────────────────────────────────

const labelSt={display:"block",fontSize:10,letterSpacing:"0.2em",textTransform:"uppercase",color:"#C8BCA4",marginBottom:6,marginTop:14};
const inputSt={width:"100%",background:"#0A0908",border:"1px solid #2A2820",borderRadius:6,color:"#E8E2D8",padding:"11px 12px",fontSize:15,outline:"none"};
const inputErrSt={...inputSt,border:"1px solid #C87E8A"};
const cardSt={background:"#161510",border:"1px solid #2A2820",borderRadius:10,padding:20};

function Btn({children,onClick,disabled,variant="gold",style={}}){
  const bases={
    gold:{background:disabled?"#1A1810":"#C8A96E",color:disabled?"#7A6A50":"#0F0E0C"},
    ghost:{background:"#1E1C18",color:"#C8A96E"},
    red:{background:"#C87E8A",color:"#0F0E0C"},
    outline:{background:"transparent",color:"#C8BCA4",border:"1px solid #2A2820"},
  };
  return(
    <button onClick={onClick} disabled={disabled} style={{width:"100%",padding:"13px 16px",border:"none",borderRadius:6,fontSize:12,letterSpacing:"0.2em",textTransform:"uppercase",cursor:disabled?"not-allowed":"pointer",marginTop:14,...bases[variant],...style}}>
      {children}
    </button>
  );
}

function Tag({children,color="#7EB8A4",bg="#1E2820"}){
  return <span style={{fontSize:9,background:bg,color,letterSpacing:"0.1em",textTransform:"uppercase",padding:"2px 6px",borderRadius:3}}>{children}</span>;
}

function MultiPicker({options,selected,onToggle,disabledMsg}){
  if(disabledMsg){
    return <div style={{...inputSt,color:"#7A6A50",fontSize:13}}>{disabledMsg}</div>;
  }
  return(
    <div style={{display:"flex",flexDirection:"column",gap:4,marginTop:6}}>
      {options.map(opt=>{
        const on=selected.includes(opt);
        return(
          <button key={opt} type="button" onClick={()=>onToggle(opt)} style={{
            display:"flex",alignItems:"center",gap:10,
            background:on?"#1E1C18":"#0A0908",
            color:on?"#E8E2D8":"#C8BCA4",
            border:`1px solid ${on?"#C8A96E":"#2A2820"}`,
            borderRadius:4,padding:"10px 12px",fontSize:14,cursor:"pointer",
            textAlign:"left",width:"100%",lineHeight:1.35
          }}>
            <span style={{
              width:18,height:18,flexShrink:0,borderRadius:3,
              border:`1px solid ${on?"#C8A96E":"#2A2820"}`,
              background:on?"#C8A96E":"transparent",
              display:"flex",alignItems:"center",justifyContent:"center",
              color:"#0F0E0C",fontSize:12,fontWeight:"bold"
            }}>{on?"✓":""}</span>
            <span style={{flex:1}}>{opt}</span>
          </button>
        );
      })}
    </div>
  );
}

function toggleIn(arr,item){return arr.includes(item)?arr.filter(x=>x!==item):[...arr,item];}

function PropertyRow({name,onRename,onDelete}){
  const [editing,setEditing]=useState(false);
  const [val,setVal]=useState(name);
  const dirty=val.trim()&&val.trim()!==name;
  if(!editing){
    return(
      <div style={{display:"flex",alignItems:"center",gap:8}}>
        <span style={{flex:1,fontSize:13,color:"#E8E2D8"}}>{name}</span>
        <button type="button" onClick={()=>{setVal(name);setEditing(true);}} style={{background:"none",border:"1px solid #2A2820",color:"#C8BCA4",cursor:"pointer",fontSize:10,padding:"5px 9px",borderRadius:3,letterSpacing:"0.1em",textTransform:"uppercase"}}>Edit</button>
        <button type="button" onClick={onDelete} style={{background:"none",border:"1px solid #2A2820",color:"#C87E8A",cursor:"pointer",fontSize:10,padding:"5px 9px",borderRadius:3,letterSpacing:"0.1em",textTransform:"uppercase"}}>Delete</button>
      </div>
    );
  }
  return(
    <div style={{display:"flex",gap:6,alignItems:"center"}}>
      <input autoFocus type="text" value={val} onChange={e=>setVal(e.target.value)} style={{...inputSt,flex:1,padding:"8px 10px",fontSize:13}}/>
      <button type="button" disabled={!dirty} onClick={()=>{onRename(val.trim());setEditing(false);}} style={{background:dirty?"#C8A96E":"#1A1810",color:dirty?"#0F0E0C":"#7A6A50",border:"none",borderRadius:3,padding:"7px 10px",fontSize:11,cursor:dirty?"pointer":"not-allowed",letterSpacing:"0.1em",textTransform:"uppercase"}}>Save</button>
      <button type="button" onClick={()=>{setVal(name);setEditing(false);}} style={{background:"none",border:"1px solid #2A2820",color:"#C8BCA4",fontSize:11,padding:"7px 10px",borderRadius:3,cursor:"pointer",letterSpacing:"0.1em",textTransform:"uppercase"}}>Cancel</button>
    </div>
  );
}

function PropertiesField({properties,setProperties,setLogs,setRecur,selected,setSelected}){
  const [editing,setEditing]=useState(false);
  const [newName,setNewName]=useState("");

  function addProp(){
    const n=newName.trim();
    if(!n||properties.includes(n))return;
    setProperties([...properties,n]);
    setNewName("");
  }
  function renameProp(oldN,newN){
    if(!newN||newN===oldN||properties.includes(newN))return;
    setProperties(properties.map(x=>x===oldN?newN:x));
    setLogs(ls=>ls.map(l=>({...l,properties:(l.properties||[]).map(x=>x===oldN?newN:x)})));
    setRecur(rs=>rs.map(r=>({...r,properties:(r.properties||[]).map(x=>x===oldN?newN:x)})));
    setSelected(selected.map(x=>x===oldN?newN:x));
  }
  function deleteProp(name){
    if(!window.confirm(`Delete "${name}"? It will be removed from existing log entries and recurring tasks, but their hours are preserved.`))return;
    setProperties(properties.filter(x=>x!==name));
    setLogs(ls=>ls.map(l=>({...l,properties:(l.properties||[]).filter(x=>x!==name)})));
    setRecur(rs=>rs.map(r=>({...r,properties:(r.properties||[]).filter(x=>x!==name)})));
    setSelected(selected.filter(x=>x!==name));
  }

  return(
    <>
      <MultiPicker
        options={properties}
        selected={selected}
        onToggle={p=>setSelected(toggleIn(selected,p))}
        disabledMsg={!properties.length?"— No properties yet. Add one below —":null}
      />
      {!editing?(
        <button type="button" onClick={()=>setEditing(true)} style={{background:"none",border:"none",color:"#C8A96E",fontSize:11,cursor:"pointer",marginTop:10,padding:"4px 0",letterSpacing:"0.15em",textTransform:"uppercase"}}>+ Add / edit properties</button>
      ):(
        <div style={{marginTop:10,padding:14,background:"#0A0908",border:"1px solid #2A2820",borderRadius:6}}>
          <div style={{fontSize:10,letterSpacing:"0.2em",textTransform:"uppercase",color:"#C8A96E",marginBottom:10}}>Manage Properties</div>
          <div style={{display:"flex",flexDirection:"column",gap:6}}>
            {properties.map(p=><PropertyRow key={p} name={p} onRename={n=>renameProp(p,n)} onDelete={()=>deleteProp(p)}/>)}
            {!properties.length&&<div style={{fontSize:12,color:"#968666"}}>No properties yet.</div>}
          </div>
          <div style={{display:"flex",gap:6,marginTop:12,paddingTop:10,borderTop:"1px solid #1E1C18"}}>
            <input type="text" value={newName} onChange={e=>setNewName(e.target.value)} onKeyDown={e=>{if(e.key==="Enter")addProp();}} placeholder="New property address..." style={{...inputSt,flex:1,padding:"8px 10px",fontSize:13}}/>
            <button type="button" onClick={addProp} disabled={!newName.trim()||properties.includes(newName.trim())} style={{background:newName.trim()&&!properties.includes(newName.trim())?"#C8A96E":"#1A1810",color:newName.trim()&&!properties.includes(newName.trim())?"#0F0E0C":"#7A6A50",border:"none",borderRadius:4,padding:"0 14px",fontSize:11,letterSpacing:"0.15em",textTransform:"uppercase",cursor:newName.trim()&&!properties.includes(newName.trim())?"pointer":"not-allowed",whiteSpace:"nowrap"}}>+ Add</button>
          </div>
          <button type="button" onClick={()=>setEditing(false)} style={{marginTop:10,background:"none",border:"1px solid #2A2820",color:"#C8BCA4",fontSize:11,letterSpacing:"0.15em",textTransform:"uppercase",padding:"8px 12px",borderRadius:4,cursor:"pointer"}}>Done</button>
        </div>
      )}
    </>
  );
}

// ─── Views ───────────────────────────────────────────────────────────────────

function LogView({logs,setLogs,recur,setRecur,properties,setProperties,form,setForm,timer,setTimer,elapsed}){
  const [descErr,setDescErr]=useState(false);
  const [filterCat,setFilterCat]=useState("all");
  const formRef=useRef(null);
  const sCat=CATEGORIES.find(c=>c.id===form.category);
  const filtered=filterCat==="all"?logs:logs.filter(l=>l.category===filterCat);
  const formReady=form.category&&form.activities.length>0&&form.properties.length>0;
  const editing=!!form.editingId;

  function validate(){if(!form.description||form.description.trim().length<10){setDescErr(true);return false;}setDescErr(false);return true;}
  function startTimer(){if(!formReady||!validate())return;setTimer({startMs:Date.now(),...form});}
  function stopTimer(){if(!timer)return;setLogs(p=>[{id:Date.now(),...timer,durationMs:Date.now()-timer.startMs,method:"timer"},...p]);setTimer(null);setForm(makeEmptyForm());setDescErr(false);}
  function addManual(){
    if(!formReady||!validate())return;
    const ms=(parseInt(form.mh||0)*60+parseInt(form.mm||0))*60000;
    if(!ms)return;
    setLogs(p=>[{id:Date.now(),...form,durationMs:ms,method:"manual"},...p]);
    setForm(makeEmptyForm());
    setDescErr(false);
  }
  function startEdit(entry){
    if(timer)setTimer(null);
    const totalMin=Math.round(entry.durationMs/60000);
    setForm({
      editingId:entry.id,
      category:entry.category||"",
      activities:entry.activities||[],
      properties:entry.properties||[],
      description:entry.description||"",
      notes:entry.notes||"",
      date:entry.date,
      endDate:entry.endDate||"",
      mh:Math.floor(totalMin/60).toString(),
      mm:(totalMin%60).toString(),
    });
    setDescErr(false);
    setTimeout(()=>formRef.current?.scrollIntoView({behavior:"smooth",block:"start"}),0);
  }
  function cancelEdit(){setForm(makeEmptyForm());setDescErr(false);}
  function saveEdit(){
    if(!formReady||!validate())return;
    const ms=(parseInt(form.mh||0)*60+parseInt(form.mm||0))*60000;
    if(!ms)return;
    setLogs(ls=>ls.map(l=>l.id===form.editingId?{
      ...l,
      category:form.category,
      activities:form.activities,
      properties:form.properties,
      date:form.date,
      endDate:form.endDate||"",
      description:form.description,
      notes:form.notes,
      durationMs:ms,
    }:l));
    setForm(makeEmptyForm());
    setDescErr(false);
  }
  function deleteEntry(id){
    if(form.editingId===id){setForm(makeEmptyForm());setDescErr(false);}
    setLogs(p=>p.filter(l=>l.id!==id));
  }

  return(
    <div className="scroll-area" style={{height:"100%",paddingBottom:20}}>
      {/* Entry form */}
      <div ref={formRef} style={{...cardSt,margin:"16px 16px 12px",borderColor:editing?"#C8A96E":"#2A3020"}}>
        <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:16}}>
          <div style={{fontSize:10,letterSpacing:"0.25em",textTransform:"uppercase",color:"#C8A96E"}}>{editing?"Editing Entry":"New Entry"}</div>
          {editing&&<button type="button" onClick={cancelEdit} style={{background:"none",border:"1px solid #2A2820",color:"#C8BCA4",fontSize:10,letterSpacing:"0.15em",textTransform:"uppercase",padding:"6px 10px",borderRadius:4,cursor:"pointer"}}>Cancel</button>}
        </div>

        <div style={{display:"flex",gap:10}}>
          <div style={{flex:1}}>
            <label style={labelSt}>Start Date</label>
            <input type="date" value={form.date} onChange={e=>setForm(f=>({...f,date:e.target.value}))} style={inputSt}/>
          </div>
          <div style={{flex:1}}>
            <label style={labelSt}>End Date <span style={{color:"#C8BCA4",textTransform:"none",letterSpacing:0}}>(optional)</span></label>
            <input type="date" value={form.endDate} min={form.date} onChange={e=>setForm(f=>({...f,endDate:e.target.value}))} style={inputSt}/>
          </div>
        </div>

        <label style={labelSt}>Category</label>
        <select value={form.category} onChange={e=>setForm(f=>({...f,category:e.target.value,activities:[]}))} style={inputSt}>
          <option value="">— Select category —</option>
          {CATEGORIES.map(c=><option key={c.id} value={c.id}>{c.icon} {c.label}</option>)}
        </select>

        <label style={labelSt}>Activities <span style={{color:"#C8BCA4",textTransform:"none",letterSpacing:0}}>(tap to select one or more)</span></label>
        <MultiPicker
          options={sCat?.activities||[]}
          selected={form.activities}
          onToggle={a=>setForm(f=>({...f,activities:toggleIn(f.activities,a)}))}
          disabledMsg={!form.category?"— Select a category first —":null}
        />

        <label style={labelSt}>Properties <span style={{color:"#C8BCA4",textTransform:"none",letterSpacing:0}}>(tap to select one or more)</span></label>
        <PropertiesField
          properties={properties}
          setProperties={setProperties}
          setLogs={setLogs}
          setRecur={setRecur}
          selected={form.properties}
          setSelected={arr=>setForm(f=>({...f,properties:arr}))}
        />

        <label style={{...labelSt,color:descErr?"#C87E8A":"#C8A96E"}}>★ Description of Work Done <span style={{color:"#C87E8A"}}>*</span></label>
        <textarea
          value={form.description}
          onChange={e=>{setForm(f=>({...f,description:e.target.value}));if(e.target.value.trim().length>=10)setDescErr(false);}}
          placeholder="e.g. Reviewed Osborn rent roll, verified HAP payments for units 2 & 4, followed up with Section 8 re unit 3 late payment"
          style={{...(descErr?inputErrSt:inputSt),height:90,resize:"none",lineHeight:1.5}}
        />
        {descErr&&<div style={{fontSize:10,color:"#C87E8A",marginTop:4}}>Required — describe specifically what you did</div>}

        <label style={labelSt}>Additional Notes (optional)</label>
        <textarea value={form.notes} onChange={e=>setForm(f=>({...f,notes:e.target.value}))} placeholder="Supporting context..." style={{...inputSt,height:48,resize:"none"}}/>

        {!editing&&(timer?(
          <div style={{marginTop:16,textAlign:"center"}}>
            <div style={{fontSize:40,color:"#C8A96E",fontVariantNumeric:"tabular-nums",letterSpacing:"0.05em",marginBottom:12}}>{fmtDur(elapsed)}</div>
            <Btn onClick={stopTimer} variant="red">■ Stop & Save</Btn>
          </div>
        ):<Btn onClick={startTimer} disabled={!formReady}>▶ Start Timer</Btn>)}

        <div style={{marginTop:16,borderTop:"1px solid #2A2820",paddingTop:16}}>
          <div style={{fontSize:10,letterSpacing:"0.2em",textTransform:"uppercase",color:"#AC9E86",marginBottom:10}}>{editing?"Hours":"Or log manually"}</div>
          <div style={{display:"flex",gap:10}}>
            <div style={{flex:1}}><label style={labelSt}>Hours</label><input type="number" min="0" value={form.mh} onChange={e=>setForm(f=>({...f,mh:e.target.value}))} style={inputSt} placeholder="0"/></div>
            <div style={{flex:1}}><label style={labelSt}>Minutes</label><input type="number" min="0" max="59" value={form.mm} onChange={e=>setForm(f=>({...f,mm:e.target.value}))} style={inputSt} placeholder="0"/></div>
          </div>
          <Btn onClick={editing?saveEdit:addManual} disabled={!formReady} variant={editing?"gold":"ghost"}>{editing?"Save Changes":"+ Add Entry"}</Btn>
        </div>
      </div>

      {/* Filter */}
      <div style={{padding:"0 16px 10px",display:"flex",gap:8,alignItems:"center"}}>
        <span style={{fontSize:10,letterSpacing:"0.15em",textTransform:"uppercase",color:"#AC9E86",flexShrink:0}}>{filtered.length} entries</span>
        <select value={filterCat} onChange={e=>setFilterCat(e.target.value)} style={{...inputSt,fontSize:11,padding:"7px 32px 7px 10px",flex:1}}>
          <option value="all">All categories</option>
          {CATEGORIES.map(c=><option key={c.id} value={c.id}>{c.icon} {c.label}</option>)}
        </select>
      </div>

      {/* Log entries */}
      <div style={{display:"flex",flexDirection:"column",gap:8,padding:"0 16px"}}>
        {!filtered.length&&<div style={{color:"#AC9E86",fontSize:13,padding:"32px 0",textAlign:"center"}}>No entries yet.<br/><span style={{fontSize:11}}>Start a timer or log manually above.</span></div>}
        {filtered.map(log=>{
          const cat=CATEGORIES.find(c=>c.id===log.category);
          const missingDesc=!log.description||log.description.trim().length<5;
          return(
            <div key={log.id} style={{...cardSt,padding:"14px 16px",borderLeft:`3px solid ${cat?.color||"#C8A96E"}`,borderColor:form.editingId===log.id?"#C8A96E":(missingDesc?"#3A2020":"#2A2820")}}>
              <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start"}}>
                <div style={{flex:1,minWidth:0}}>
                  <div style={{display:"flex",gap:6,alignItems:"center",flexWrap:"wrap",marginBottom:4}}>
                    <span style={{fontSize:11,color:cat?.color}}>{cat?.icon} {cat?.label}</span>
                  </div>
                  <div style={{display:"flex",gap:6,alignItems:"center",flexWrap:"wrap",marginBottom:6}}>
                    <span style={{fontSize:10,color:"#C8BCA4"}}>{fmtRange(log.date,log.endDate)}</span>
                    {log.method==="recurring"&&<Tag color="#7EB8A4" bg="#1E2820">↻ recurring</Tag>}
                    {log.method==="manual"&&<Tag color="#AC9E86" bg="#1A1818">manual</Tag>}
                    {missingDesc&&<Tag color="#C87E8A" bg="#2A1818">⚠ needs description</Tag>}
                  </div>
                  <div style={{fontSize:14,color:"#E8E2D8",marginBottom:4,lineHeight:1.35}}>{(log.activities||[]).join(" · ")}</div>
                  <div style={{fontSize:11,color:"#B8A890",marginBottom:log.description?6:0,lineHeight:1.35}}>{(log.properties||[]).join(" · ")}</div>
                  {log.description&&<div style={{fontSize:12,color:"#B8C8B0",lineHeight:1.5,borderLeft:"2px solid #2A3828",paddingLeft:10}}>{log.description}</div>}
                  {log.notes&&<div style={{fontSize:11,color:"#AC9E86",marginTop:4,fontStyle:"italic"}}>{log.notes}</div>}
                </div>
                <div style={{textAlign:"right",flexShrink:0,marginLeft:12,display:"flex",flexDirection:"column",alignItems:"flex-end",gap:6}}>
                  <div style={{fontSize:20,color:"#C8A96E",fontVariantNumeric:"tabular-nums"}}>{fmtHrs(log.durationMs)}h</div>
                  <div style={{display:"flex",gap:4,alignItems:"center"}}>
                    <button onClick={()=>startEdit(log)} style={{background:"none",border:"1px solid #2A2820",color:"#C8BCA4",cursor:"pointer",fontSize:10,padding:"4px 8px",borderRadius:3,letterSpacing:"0.1em",textTransform:"uppercase"}}>Edit</button>
                    <button onClick={()=>deleteEntry(log.id)} style={{background:"none",border:"none",color:"#7A6A50",cursor:"pointer",fontSize:20,lineHeight:1,padding:"0 4px"}}>×</button>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function RecurView({recur,setRecur,logs,setLogs,properties,setProperties}){
  const [showForm,setShowForm]=useState(false);
  const [rf,setRf]=useState(makeEmptyRf);
  const rCat=CATEGORIES.find(c=>c.id===rf.category);
  const rfReady=rf.category&&rf.activities.length>0&&rf.properties.length>0;

  function addRecur(){
    const ms=(parseInt(rf.hours||0)*60+parseInt(rf.minutes||0))*60000;
    if(!rfReady||!ms||!rf.description)return;
    setRecur(p=>[...p,{id:Date.now(),category:rf.category,activities:rf.activities,properties:rf.properties,description:rf.description,notes:rf.notes,durationMs:ms,startDate:rf.startDate,endDate:rf.endDate||"",freq:rf.freq||"weekly"}]);
    setRf(makeEmptyRf());
    setShowForm(false);
  }

  return(
    <div className="scroll-area" style={{height:"100%",paddingBottom:20}}>
      <div style={{padding:"16px 16px 0",display:"flex",justifyContent:"space-between",alignItems:"center"}}>
        <div>
          <div style={{fontSize:10,letterSpacing:"0.25em",textTransform:"uppercase",color:"#C8BCA4"}}>Recurring Tasks</div>
          <div style={{fontSize:11,color:"#AC9E86",marginTop:4}}>Auto-logged weekly or monthly as time passes</div>
        </div>
        <button onClick={()=>setShowForm(!showForm)} style={{background:showForm?"#2A2820":"#C8A96E",color:showForm?"#C8BCA4":"#0F0E0C",border:"none",borderRadius:6,padding:"9px 14px",fontSize:11,letterSpacing:"0.15em",textTransform:"uppercase",cursor:"pointer"}}>
          {showForm?"Cancel":"+ Add"}
        </button>
      </div>

      {showForm&&(
        <div style={{...cardSt,margin:"16px 16px 8px",borderColor:"#C8A96E"}}>
          <div style={{fontSize:10,letterSpacing:"0.2em",textTransform:"uppercase",color:"#C8A96E",marginBottom:14}}>New Recurring Task</div>
          <label style={labelSt}>Category</label>
          <select value={rf.category} onChange={e=>setRf(f=>({...f,category:e.target.value,activities:[]}))} style={inputSt}>
            <option value="">— Select —</option>
            {CATEGORIES.map(c=><option key={c.id} value={c.id}>{c.icon} {c.label}</option>)}
          </select>
          <label style={labelSt}>Activities <span style={{color:"#C8BCA4",textTransform:"none",letterSpacing:0}}>(tap to select one or more)</span></label>
          <MultiPicker
            options={rCat?.activities||[]}
            selected={rf.activities}
            onToggle={a=>setRf(f=>({...f,activities:toggleIn(f.activities,a)}))}
            disabledMsg={!rf.category?"— Select a category first —":null}
          />
          <label style={labelSt}>Properties <span style={{color:"#C8BCA4",textTransform:"none",letterSpacing:0}}>(tap to select one or more)</span></label>
          <PropertiesField
            properties={properties}
            setProperties={setProperties}
            setLogs={setLogs}
            setRecur={setRecur}
            selected={rf.properties}
            setSelected={arr=>setRf(f=>({...f,properties:arr}))}
          />
          <label style={labelSt}>Frequency</label>
          <div style={{display:"flex",gap:8,marginBottom:4}}>
            {[["weekly","↻ Weekly"],["monthly","↻ Monthly"]].map(([val,lbl])=>(
              <button key={val} type="button" onClick={()=>setRf(f=>({...f,freq:val}))}
                style={{flex:1,padding:"10px",borderRadius:6,fontSize:12,cursor:"pointer",fontFamily:"inherit",
                  border:`1px solid ${rf.freq===val?"#C8A96E":"#2A2820"}`,
                  background:rf.freq===val?"#C8A96E":"#0A0908",
                  color:rf.freq===val?"#0F0E0C":"#C8BCA4"}}>{lbl}</button>
            ))}
          </div>
          <div style={{display:"flex",gap:10}}>
            <div style={{flex:1}}>
              <label style={labelSt}>Start Date</label>
              <input type="date" value={rf.startDate} onChange={e=>setRf(f=>({...f,startDate:e.target.value}))} style={inputSt}/>
            </div>
            <div style={{flex:1}}>
              <label style={labelSt}>End Date <span style={{color:"#C8BCA4",textTransform:"none",letterSpacing:0}}>(optional)</span></label>
              <input type="date" value={rf.endDate} min={rf.startDate} onChange={e=>setRf(f=>({...f,endDate:e.target.value}))} style={inputSt}/>
            </div>
          </div>
          <div style={{display:"flex",gap:10}}>
            <div style={{flex:1}}><label style={labelSt}>Hours / {rf.freq==="monthly"?"month":"week"}</label><input type="number" min="0" value={rf.hours} onChange={e=>setRf(f=>({...f,hours:e.target.value}))} style={inputSt} placeholder="0"/></div>
            <div style={{flex:1}}><label style={labelSt}>Minutes / {rf.freq==="monthly"?"month":"week"}</label><input type="number" min="0" max="59" value={rf.minutes} onChange={e=>setRf(f=>({...f,minutes:e.target.value}))} style={inputSt} placeholder="0"/></div>
          </div>
          <label style={{...labelSt,color:"#C8A96E"}}>★ Description of Work Done <span style={{color:"#C87E8A"}}>*</span></label>
          <textarea value={rf.description} onChange={e=>setRf(f=>({...f,description:e.target.value}))} placeholder="e.g. Weekly rent roll review, verify HAP payments, log discrepancies, follow up on late items" style={{...inputSt,height:80,resize:"none",lineHeight:1.5}}/>
          <label style={labelSt}>Additional Notes (optional)</label>
          <input type="text" value={rf.notes} onChange={e=>setRf(f=>({...f,notes:e.target.value}))} style={inputSt} placeholder="Supporting context..."/>
          <Btn onClick={addRecur} disabled={!rfReady||(!rf.hours&&!rf.minutes)||!rf.description}>Save Recurring Task</Btn>
        </div>
      )}

      {!recur.length&&!showForm&&(
        <div style={{color:"#AC9E86",fontSize:13,padding:"40px 16px",textAlign:"center"}}>
          No recurring tasks yet.<br/>
          <span style={{fontSize:11,color:"#7A6A50"}}>Add weekly tasks like rent review, bookkeeping, or property walk-throughs.</span>
        </div>
      )}

      <div style={{display:"flex",flexDirection:"column",gap:8,padding:"8px 16px"}}>
        {recur.map(task=>{
          const cat=CATEGORIES.find(c=>c.id===task.category);
          const isMonthly=task.freq==="monthly";
          const occ=occurrences(task);
          const unit=isMonthly?"month":"week";
          return(
            <div key={task.id} style={{...cardSt,padding:"14px 16px",borderLeft:`3px solid ${cat?.color||"#C8A96E"}`}}>
              <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start"}}>
                <div style={{flex:1,minWidth:0}}>
                  <div style={{display:"flex",gap:6,flexWrap:"wrap",marginBottom:6}}>
                    <Tag color="#7EB8A4" bg="#1E2820">↻ {isMonthly?"monthly":"weekly"}</Tag>
                    <span style={{fontSize:11,color:cat?.color}}>{cat?.icon} {cat?.label}</span>
                  </div>
                  <div style={{fontSize:14,color:"#E8E2D8",marginBottom:3,lineHeight:1.35}}>{(task.activities||[]).join(" · ")}</div>
                  <div style={{fontSize:11,color:"#B8A890",marginBottom:6,lineHeight:1.35}}>{(task.properties||[]).join(" · ")}</div>
                  {task.description&&<div style={{fontSize:12,color:"#B8C8B0",lineHeight:1.5,borderLeft:"2px solid #2A3828",paddingLeft:10,marginBottom:6}}>{task.description}</div>}
                  <div style={{fontSize:10,color:"#968666"}}>{task.endDate?`${fmtDate(task.startDate)} – ${fmtDate(task.endDate)}`:`Since ${fmtDate(task.startDate)}`} · {occ.length} {unit}{occ.length!==1?"s":""} · {fmtHrs(task.durationMs*occ.length)} hrs total</div>
                </div>
                <div style={{textAlign:"right",flexShrink:0,marginLeft:12}}>
                  <div style={{fontSize:20,color:"#C8A96E"}}>{fmtHrs(task.durationMs)}h</div>
                  <div style={{fontSize:9,color:"#AC9E86",letterSpacing:"0.1em",textTransform:"uppercase"}}>/ {unit}</div>
                  <button onClick={()=>{setRecur(p=>p.filter(t=>t.id!==task.id));setLogs(p=>p.filter(l=>l.recurId!==task.id));}} style={{marginTop:8,background:"none",border:"1px solid #2A2820",color:"#C8BCA4",cursor:"pointer",fontSize:9,padding:"4px 8px",borderRadius:3,letterSpacing:"0.1em",textTransform:"uppercase"}}>Remove</button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function SummaryView({logs,totalHrs,totalMs,exportCSV}){
  return(
    <div className="scroll-area" style={{height:"100%",paddingBottom:20}}>
      <div style={{padding:"16px 16px 8px"}}>
        <div style={{fontSize:10,letterSpacing:"0.25em",textTransform:"uppercase",color:"#C8BCA4",marginBottom:14}}>Hours by Category — {new Date().getFullYear()}</div>
      </div>
      <div style={{display:"flex",flexDirection:"column",gap:8,padding:"0 16px"}}>
        {CATEGORIES.map(c=>{
          const ms=logs.filter(l=>l.category===c.id).reduce((a,l)=>a+l.durationMs,0);
          return(
            <div key={c.id} style={{...cardSt,padding:"14px 16px"}}>
              <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:8}}>
                <span style={{fontSize:13,color:c.color}}>{c.icon} {c.label}</span>
                <span style={{fontSize:16,color:"#E8E2D8",fontVariantNumeric:"tabular-nums"}}>{(ms/3600000).toFixed(2)}h</span>
              </div>
              <div style={{height:3,background:"#2A2820",borderRadius:2}}>
                <div style={{height:3,borderRadius:2,background:c.color,width:totalMs?`${(ms/totalMs)*100}%`:"0%",transition:"width 0.4s"}}/>
              </div>
              <div style={{fontSize:10,color:"#AC9E86",marginTop:5}}>{totalMs?`${((ms/totalMs)*100).toFixed(1)}% of total`:"—"}</div>
              {ms>0&&(
                <div style={{marginTop:10,paddingTop:10,borderTop:"1px solid #1E1C18"}}>
                  {c.activities.map(act=>{
                    const ams=logs.filter(l=>l.category===c.id&&(l.activities||[]).includes(act)).reduce((a,l)=>a+l.durationMs/(l.activities?.length||1),0);
                    if(!ams)return null;
                    return<div key={act} style={{display:"flex",justifyContent:"space-between",fontSize:11,color:"#C8BCA4",marginTop:4,gap:8}}><span style={{flex:1}}>{act}</span><span style={{color:"#E8E2D8",flexShrink:0}}>{(ams/3600000).toFixed(2)}h</span></div>;
                  })}
                </div>
              )}
            </div>
          );
        })}
        <div style={{...cardSt,border:"1px solid #C8A96E",display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:8}}>
          <div><div style={{fontSize:10,color:"#C8BCA4",letterSpacing:"0.1em",textTransform:"uppercase"}}>Total Logged</div><div style={{fontSize:28,color:"#C8A96E",marginTop:4}}>{totalHrs.toFixed(2)} hrs</div></div>
          <div style={{textAlign:"right"}}><div style={{fontSize:10,color:"#C8BCA4",letterSpacing:"0.1em",textTransform:"uppercase"}}>Remaining</div><div style={{fontSize:28,color:totalHrs>=750?"#7EB8A4":"#E8E2D8",marginTop:4}}>{totalHrs>=750?"✓ Done":`${(750-totalHrs).toFixed(1)} hrs`}</div></div>
        </div>
        <button onClick={exportCSV} style={{width:"100%",padding:14,background:"transparent",color:"#C8BCA4",border:"1px solid #2A2820",borderRadius:6,fontSize:11,letterSpacing:"0.2em",textTransform:"uppercase",cursor:"pointer",marginBottom:8}}>Export CSV</button>
      </div>
    </div>
  );
}

function AttestView({logs,totalHrs,attest,setAttest}){
  const signRef=useRef(null);

  function save(){const sig=signRef.current?.value?.trim();if(!sig)return;setAttest(a=>({...a,signed:sig,signDate:todayStr()}));}

  function printDoc(){
    const year=new Date().getFullYear();
    const html=`<!DOCTYPE html><html><head><title>REP Attestation ${year}</title>
    <style>body{font-family:Georgia,serif;max-width:720px;margin:60px auto;color:#111;line-height:1.7;font-size:13px}h1{font-size:20px;border-bottom:2px solid #111;padding-bottom:8px;margin-bottom:20px}h2{font-size:13px;margin-top:32px;text-transform:uppercase;letter-spacing:0.1em;border-bottom:1px solid #ccc;padding-bottom:4px}table{width:100%;border-collapse:collapse;font-size:11px;margin-top:12px}th{background:#f5f5f5;border:1px solid #ccc;padding:6px 8px;text-align:left}td{border:1px solid #ccc;padding:6px 8px;vertical-align:top}.sig{margin-top:48px;border-top:2px solid #111;padding-top:16px}.attest{background:#f9f9f9;border:1px solid #ccc;padding:16px;margin-top:12px;font-size:12px}</style>
    </head><body>
    <h1>Real Estate Professional Hour Log — Tax Year ${year}</h1>
    <p><strong>Taxpayer:</strong> ${attest.name}</p>
    <p><strong>Entity:</strong> ${attest.entityName}</p>
    <p><strong>Total Hours Logged:</strong> ${totalHrs.toFixed(2)}</p>
    <p><strong>IRS 750-Hour Threshold:</strong> ${totalHrs>=750?"✓ Met (qualified)":"Not yet met"}</p>
    <h2>Hour Log Detail</h2>
    <table><thead><tr><th>Date</th><th>Category</th><th>Activity</th><th>Property</th><th>Hours</th><th>Description of Work</th></tr></thead>
    <tbody>${logs.map(l=>{const cat=CATEGORIES.find(c=>c.id===l.category)?.label||l.category;return`<tr><td>${fmtRange(l.date,l.endDate)}</td><td>${cat}</td><td>${(l.activities||[]).join("; ")}</td><td>${(l.properties||[]).join("; ")}</td><td>${fmtHrs(l.durationMs)}</td><td>${l.description||"—"}</td></tr>`;}).join("")}</tbody></table>
    <h2>Declaration Under Penalty of Perjury</h2>
    <div class="attest">I, <strong>${attest.name}</strong>, declare under penalty of perjury that the information in this Real Estate Professional Hour Log is true, correct, and complete to the best of my knowledge and belief. The activities recorded were performed by me in connection with real property trade or business activities as defined under IRC §469(c)(7). During tax year ${year}, I spent more than 750 hours in real property trades or businesses in which I materially participated, and more than half of my personal services for the year were performed in real property trades or businesses in which I materially participated.</div>
    <div class="sig">
    <p style="font-size:22px;font-style:italic;margin-bottom:4px">${attest.signed}</p>
    <p><strong>Printed Name:</strong> ${attest.name}</p>
    <p><strong>Title:</strong> Managing Member, ${attest.entityName}</p>
    <p><strong>Date:</strong> ${fmtDate(attest.signDate)}</p>
    </div></body></html>`;
    const w=window.open("","_blank");w.document.write(html);w.document.close();w.print();
  }

  return(
    <div className="scroll-area" style={{height:"100%",paddingBottom:20}}>
      <div style={{padding:"16px 16px 8px"}}>
        <div style={{fontSize:10,letterSpacing:"0.25em",textTransform:"uppercase",color:"#C8BCA4"}}>Year-End Attestation</div>
        <div style={{fontSize:12,color:"#AC9E86",marginTop:4}}>Required for IRS substantiation. Sign and save with your tax documentation.</div>
      </div>
      <div style={{display:"flex",flexDirection:"column",gap:10,padding:"8px 16px"}}>

        {/* Taxpayer info */}
        <div style={cardSt}>
          <div style={{fontSize:10,letterSpacing:"0.2em",textTransform:"uppercase",color:"#C8BCA4",marginBottom:14}}>Taxpayer Information</div>
          <label style={labelSt}>Full Legal Name</label>
          <input type="text" value={attest.name} onChange={e=>setAttest(a=>({...a,name:e.target.value}))} style={inputSt}/>
          <label style={labelSt}>Entity Name</label>
          <input type="text" value={attest.entityName} onChange={e=>setAttest(a=>({...a,entityName:e.target.value}))} style={inputSt}/>
        </div>

        {/* Declaration */}
        <div style={{...cardSt,borderColor:"#2A3828"}}>
          <div style={{fontSize:10,letterSpacing:"0.2em",textTransform:"uppercase",color:"#7EB8A4",marginBottom:14}}>Declaration Under Penalty of Perjury</div>
          <div style={{fontSize:12,color:"#B8C8B0",lineHeight:1.8,background:"#0F1510",border:"1px solid #1E2820",borderRadius:6,padding:16}}>
            I, <strong style={{color:"#E8E2D8"}}>{attest.name||"[Your Name]"}</strong>, declare under penalty of perjury that the information in this Real Estate Professional Hour Log is true, correct, and complete to the best of my knowledge and belief.
            <br/><br/>
            The activities recorded were performed by me in connection with real property trade or business activities as defined under <strong style={{color:"#E8E2D8"}}>IRC §469(c)(7)</strong>. During tax year <strong style={{color:"#E8E2D8"}}>{new Date().getFullYear()}</strong>, I spent more than 750 hours in real property trades or businesses in which I materially participated, and more than half of my total personal services for the year were performed in real property trades or businesses in which I materially participated.
            <br/><br/>
            Total hours logged: <strong style={{color:"#C8A96E"}}>{totalHrs.toFixed(2)} hours</strong><br/>
            Entity: <strong style={{color:"#E8E2D8"}}>{attest.entityName||"[Entity]"}</strong><br/>
            Role: <strong style={{color:"#E8E2D8"}}>Managing Member</strong>
          </div>
        </div>

        {/* Signature */}
        <div style={cardSt}>
          <div style={{fontSize:10,letterSpacing:"0.2em",textTransform:"uppercase",color:"#C8BCA4",marginBottom:14}}>Signature</div>
          {attest.signed?(
            <div>
              <div style={{fontSize:10,color:"#AC9E86",marginBottom:8}}>Signed {fmtDate(attest.signDate)}</div>
              <div style={{fontSize:28,color:"#C8A96E",borderBottom:"1px solid #968666",paddingBottom:8,marginBottom:12,fontStyle:"italic"}}>{attest.signed}</div>
              <div style={{fontSize:12,color:"#C8BCA4"}}>{attest.name} — Managing Member, {attest.entityName}</div>
              <button onClick={()=>setAttest(a=>({...a,signed:"",signDate:""}))} style={{marginTop:14,background:"none",border:"1px solid #2A2820",color:"#C8BCA4",cursor:"pointer",fontSize:10,padding:"7px 12px",borderRadius:4,letterSpacing:"0.1em",textTransform:"uppercase"}}>Clear & Re-sign</button>
            </div>
          ):(
            <div>
              <div style={{fontSize:12,color:"#AC9E86",marginBottom:12}}>Type your full legal name to sign. This constitutes a declaration under penalty of perjury.</div>
              <label style={labelSt}>Type Full Name to Sign</label>
              <input ref={signRef} type="text" placeholder={attest.name||"Full legal name..."} style={{...inputSt,fontSize:18,fontStyle:"italic",borderColor:"#C8A96E"}}/>
              <Btn onClick={save}>Sign Attestation</Btn>
            </div>
          )}
        </div>

        <button onClick={printDoc} disabled={!attest.signed} style={{width:"100%",padding:14,background:"transparent",color:attest.signed?"#C8A96E":"#7A6A50",border:`1px solid ${attest.signed?"#C8A96E":"#2A2820"}`,borderRadius:6,fontSize:11,letterSpacing:"0.2em",textTransform:"uppercase",cursor:attest.signed?"pointer":"not-allowed",marginBottom:4}}>
          Print / Save as PDF
        </button>
        {!attest.signed&&<div style={{fontSize:11,color:"#AC9E86",textAlign:"center",marginBottom:8}}>Sign above before printing</div>}
      </div>
    </div>
  );
}

// ─── Root App ────────────────────────────────────────────────────────────────

function migrate(entry){
  return{
    ...entry,
    activities: entry.activities || (entry.activity?[entry.activity]:[]),
    properties: entry.properties || (entry.property?[entry.property]:[]),
  };
}

// Shown when a user opens a password-reset link. The recovery session is
// already established; here they just set a new password.
function ResetPassword({onDone,onCancel}){
  const [pw,setPw]=useState("");
  const [pw2,setPw2]=useState("");
  const [busy,setBusy]=useState(false);
  const [err,setErr]=useState("");
  const [msg,setMsg]=useState("");
  const inputSt={width:"100%",background:"#0A0908",border:"1px solid #2A2820",borderRadius:6,color:"#E8E2D8",padding:"12px",fontSize:15,outline:"none",fontFamily:"inherit"};
  const labelSt={display:"block",fontSize:10,letterSpacing:"0.2em",textTransform:"uppercase",color:"#C8BCA4",marginBottom:6,marginTop:16};
  async function submit(e){
    e?.preventDefault();setErr("");setMsg("");
    if(pw.length<6){setErr("Password must be at least 6 characters.");return;}
    if(pw!==pw2){setErr("Passwords don't match.");return;}
    setBusy(true);
    try{
      const {error}=await supabase.auth.updateUser({password:pw});
      if(error)throw error;
      setMsg("Password updated. You're all set.");
      setTimeout(()=>onDone&&onDone(),900);
    }catch(e2){setErr(e2.message||"Could not update password.");}
    finally{setBusy(false);}
  }
  return(
    <div style={{minHeight:"100vh",background:"#0F0E0C",color:"#E8E2D8",display:"flex",alignItems:"center",justifyContent:"center",padding:"24px",fontFamily:"Georgia, 'Times New Roman', serif"}}>
      <form style={{width:"100%",maxWidth:380,background:"#161510",border:"1px solid #2A2820",borderRadius:12,padding:28}} onSubmit={submit}>
        <div style={{fontSize:9,letterSpacing:"0.25em",textTransform:"uppercase",color:"#AC9E86",marginBottom:2}}>DFM Capital LLC</div>
        <div style={{fontSize:22,color:"#E8E2D8",lineHeight:1.1}}>Set a New Password</div>
        <div style={{fontSize:12,color:"#AC9E86",marginTop:6}}>Choose a new password for your account.</div>
        <label style={labelSt}>New Password</label>
        <input type="password" autoComplete="new-password" value={pw} onChange={e=>setPw(e.target.value)} style={inputSt} placeholder="••••••••"/>
        <label style={labelSt}>Confirm Password</label>
        <input type="password" autoComplete="new-password" value={pw2} onChange={e=>setPw2(e.target.value)} style={inputSt} placeholder="••••••••"/>
        {err&&<div style={{fontSize:12,color:"#C87E8A",marginTop:12}}>{err}</div>}
        {msg&&<div style={{fontSize:12,color:"#7EB8A4",marginTop:12}}>{msg}</div>}
        <button type="submit" disabled={busy} style={{width:"100%",marginTop:20,padding:"13px",border:"none",borderRadius:6,fontSize:12,letterSpacing:"0.2em",textTransform:"uppercase",cursor:busy?"not-allowed":"pointer",background:busy?"#1A1810":"#C8A96E",color:busy?"#7A6A50":"#0F0E0C",fontFamily:"inherit"}}>{busy?"…":"Update Password"}</button>
        <button type="button" onClick={onCancel} style={{width:"100%",marginTop:12,background:"none",border:"none",color:"#AC9E86",fontSize:11,cursor:"pointer",fontFamily:"inherit"}}>Cancel</button>
      </form>
    </div>
  );
}

export default function App(){
  const [logs,setLogs]=useState(()=>LS.get("rep_logs",[]).map(migrate));
  const [recur,setRecur]=useState(()=>LS.get("rep_recur",[]).map(migrate));
  const [attest,setAttest]=useState(()=>LS.get("rep_attest",{name:"Dominick",entityName:"DFM Capital LLC",signed:"",signDate:""}));
  const [timer,setTimer]=useState(null);
  const [elapsed,setElapsed]=useState(0);
  const [view,setView]=useState("log");
  const [properties,setProperties]=useState(()=>{const saved=LS.get("rep_properties",null);return Array.isArray(saved)&&saved.length?saved:DEFAULT_PROPERTIES;});
  const [form,setForm]=useState(makeEmptyForm);
  const tick=useRef(null);

  // ── Cloud sync (Supabase) ──────────────────────────────────────────────────
  const [session,setSession]=useState(null);
  const [authReady,setAuthReady]=useState(!hasSupabase);
  const [synced,setSynced]=useState(false);
  const [syncState,setSyncState]=useState("idle");
  const [ownerUserId,setOwnerUserId]=useState(null); // set when logged in as a team member
  const [recovery,setRecovery]=useState(false); // true while completing a password-reset link
  const syncTimer=useRef(null);

  // Track auth session
  useEffect(()=>{
    if(!hasSupabase)return;

    // Password-reset links arrive as #access_token=...&type=recovery. We keep
    // detectSessionInUrl:false (so a copied session URL can't silently log
    // anyone in), and instead honor the URL tokens ONLY when type=recovery —
    // establishing a short-lived session just long enough to set a new password.
    const hash=window.location.hash.startsWith("#")?window.location.hash.slice(1):"";
    const hp=new URLSearchParams(hash);
    if(hp.get("type")==="recovery"&&hp.get("access_token")){
      setRecovery(true);
      supabase.auth.setSession({
        access_token:hp.get("access_token"),
        refresh_token:hp.get("refresh_token")||"",
      }).then(({data})=>{setSession(data.session);setAuthReady(true);})
        .catch(()=>setAuthReady(true));
      // Strip the tokens from the address bar so they aren't left in history.
      window.history.replaceState(null,"",window.location.pathname+window.location.search);
      return;
    }

    supabase.auth.getSession().then(({data})=>{setSession(data.session);setAuthReady(true);});
    const {data:sub}=supabase.auth.onAuthStateChange((e,s)=>{
      if(e==="PASSWORD_RECOVERY")setRecovery(true);
      setSession(s);setAuthReady(true);if(!s){setSynced(false);setOwnerUserId(null);}
    });
    return()=>sub.subscription.unsubscribe();
  },[]);

  // On login: check team membership, then pull data.
  useEffect(()=>{
    if(!hasSupabase||!session){return;}
    let cancelled=false;
    (async()=>{
      const uid=session.user.id;
      const email=session.user.email;

      // 1. Check if this user was invited as a team member (unclaimed invite).
      //    If so, claim it by setting member_id.
      const {data:unclaimed}=await supabase.from("team_members")
        .select("owner_id").eq("member_email",email).is("member_id",null).maybeSingle();
      if(unclaimed){
        await supabase.from("team_members")
          .update({member_id:uid,accepted_at:new Date().toISOString()})
          .eq("owner_id",unclaimed.owner_id).eq("member_email",email);
      }

      // 2. Check if this user is an accepted team member of someone.
      const {data:membership}=await supabase.from("team_members")
        .select("owner_id").eq("member_id",uid).not("accepted_at","is",null).maybeSingle();
      const dataUserId=membership?membership.owner_id:uid;
      if(!cancelled)setOwnerUserId(membership?membership.owner_id:null);

      // 3. Load data (owner's row if member, own row if owner).
      const {data,error}=await supabase.from("user_data")
        .select("logs,recur,properties,attest").eq("user_id",dataUserId).maybeSingle();
      if(cancelled)return;
      if(error){setSyncState("error");return;}
      if(!data&&!membership){
        await supabase.from("user_data").insert({user_id:uid,logs,recur,properties,attest});
      }else if(data){
        setLogs((data.logs||[]).map(migrate));
        setRecur((data.recur||[]).map(migrate));
        if(Array.isArray(data.properties)&&data.properties.length)setProperties(data.properties);
        if(data.attest&&Object.keys(data.attest).length)setAttest(data.attest);
      }
      if(!cancelled)setSynced(true);
    })();
    return()=>{cancelled=true;};
  },[session]); // eslint-disable-line

  // Push changes to cloud (debounced). Uses owner's row if member.
  useEffect(()=>{
    if(!hasSupabase||!session||!synced){return;}
    const dataUserId=ownerUserId||session.user.id;
    setSyncState("saving");
    clearTimeout(syncTimer.current);
    syncTimer.current=setTimeout(async()=>{
      const {error}=await supabase.from("user_data")
        .upsert({user_id:dataUserId,logs,recur,properties,attest},{onConflict:"user_id"});
      setSyncState(error?(navigator.onLine?"error":"offline"):"saved");
    },800);
    return()=>clearTimeout(syncTimer.current);
  },[logs,recur,properties,attest,synced,session,ownerUserId]); // eslint-disable-line

  async function signOut(){
    if(!hasSupabase)return;
    try{
      // scope:'local' clears this device's session without a server round-trip
      // that can hang/fail (offline, expired token) and leave you stuck signed in.
      await supabase.auth.signOut({scope:'local'});
    }catch(e){
      console.warn('signOut error',e);
    }finally{
      // Fallback: always drop back to the login screen even if the call errored.
      setSession(null);setSynced(false);setOwnerUserId(null);
    }
  }

  // Global sign-out: revokes EVERY session/device for this account (scope:'global').
  // Use this to kick out anyone who got hold of a session token.
  async function signOutEverywhere(){
    if(!hasSupabase)return;
    try{
      await supabase.auth.signOut({scope:'global'});
    }catch(e){
      console.warn('signOutEverywhere error',e);
    }finally{
      setSession(null);setSynced(false);setOwnerUserId(null);
    }
  }

  // localStorage acts as an instant-paint offline cache.
  useEffect(()=>{LS.set("rep_logs",logs);},[logs]);
  useEffect(()=>{LS.set("rep_recur",recur);},[recur]);
  useEffect(()=>{LS.set("rep_attest",attest);},[attest]);
  useEffect(()=>{LS.set("rep_properties",properties);},[properties]);

  // Auto-log recurring
  useEffect(()=>{
    if(!recur.length)return;
    const newEntries=[];
    recur.forEach(task=>{
      occurrences(task).forEach(date=>{
        const wk=weekKey(date);
        // Monthly tasks key off the year-month so each month logs once;
        // weekly tasks key off the ISO week as before.
        const occKey=task.freq==="monthly"?date.slice(0,7):wk;
        if(!logs.some(l=>l.recurId===task.id&&(l.occKey||l.wk)===occKey)){
          newEntries.push({id:Date.now()+Math.random(),date,category:task.category,activities:task.activities||[],properties:task.properties||[],description:task.description,notes:task.notes,durationMs:task.durationMs,method:"recurring",recurId:task.id,wk,occKey});
        }
      });
    });
    if(newEntries.length)setLogs(prev=>[...newEntries,...prev].sort((a,b)=>b.date.localeCompare(a.date)));
  },[recur]); // eslint-disable-line

  useEffect(()=>{
    if(timer){tick.current=setInterval(()=>setElapsed(Date.now()-timer.startMs),1000);}
    else{clearInterval(tick.current);setElapsed(0);}
    return()=>clearInterval(tick.current);
  },[timer]);

  const totalMs=logs.reduce((a,l)=>a+l.durationMs,0);
  const totalHrs=totalMs/3600000;
  const doy=Math.ceil((new Date()-new Date(new Date().getFullYear(),0,1))/86400000);
  const onPace=totalHrs/(doy/365)>=750;

  function exportCSV(){
    const rows=logs.map(l=>{const cat=CATEGORIES.find(c=>c.id===l.category)?.label||l.category;return`"${l.date}","${l.endDate||""}","${cat}","${(l.activities||[]).join("; ")}","${(l.properties||[]).join("; ")}","${fmtHrs(l.durationMs)}","${(l.description||"").replace(/"/g,'""')}","${(l.notes||"").replace(/"/g,'""')}","${l.method}"`;});
    const b=new Blob(["Start Date,End Date,Category,Activity,Property,Hours,Description of Work,Notes,Method\n"+rows.join("\n")],{type:"text/csv"});
    const a=document.createElement("a");a.href=URL.createObjectURL(b);a.download=`REP_Hours_${new Date().getFullYear()}.csv`;a.click();
  }

  const NAV=[
    {id:"log",icon:"⏱",label:"Log"},
    {id:"recur",icon:"↻",label:`Recurring${recur.length?` (${recur.length})`:""}`},
    {id:"summary",icon:"📊",label:"Summary"},
    {id:"attest",icon:attest.signed?"✓":"📝",label:"Attest"},
    {id:"account",icon:"👤",label:"Account"},
  ];

  // Auth gate (only when cloud is configured)
  if(hasSupabase&&!authReady){
    return <div style={{height:"100vh",display:"flex",alignItems:"center",justifyContent:"center",background:"#0F0E0C",color:"#AC9E86",fontFamily:"Georgia,serif",fontSize:13,letterSpacing:"0.15em",textTransform:"uppercase"}}>Loading…</div>;
  }
  // Completing a password-reset link: show the set-new-password screen.
  if(hasSupabase&&recovery&&session){
    return <ResetPassword onDone={()=>{setRecovery(false);}} onCancel={async()=>{setRecovery(false);await signOut();}}/>;
  }
  if(hasSupabase&&!session){
    return <Auth/>;
  }

  const syncLabel={idle:"",saving:"⟳ Saving…",saved:"✓ Synced",error:"⚠ Sync error",offline:"○ Offline — cached"}[syncState];
  const syncColor={idle:"#AC9E86",saving:"#C8BCA4",saved:"#7EB8A4",error:"#C87E8A",offline:"#C8A96E"}[syncState];

  return(
    <div style={{height:"100vh",display:"flex",flexDirection:"column",background:"#0F0E0C"}}>

      {/* Header */}
      <div style={{background:"#0F0E0C",borderBottom:"1px solid #2A2820",padding:"14px 16px 12px",flexShrink:0}}>
        <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
          <div>
            <div style={{fontSize:9,letterSpacing:"0.25em",textTransform:"uppercase",color:"#AC9E86",marginBottom:2}}>DFM Capital LLC</div>
            <div style={{fontSize:18,color:"#E8E2D8",lineHeight:1.1}}>REP Hour Log</div>
            {hasSupabase&&session&&<div style={{fontSize:11,color:"#C8A96E",marginTop:3}}>{displayName(session.user)}</div>}
          </div>
          <div style={{textAlign:"right"}}>
            <div style={{fontSize:28,fontWeight:"bold",color:"#C8A96E",lineHeight:1}}>{totalHrs.toFixed(1)}<span style={{fontSize:12,color:"#C8BCA4",marginLeft:3}}>/ 750h</span></div>
            <div style={{fontSize:9,letterSpacing:"0.15em",textTransform:"uppercase",color:onPace?"#7EB8A4":"#C87E8A",marginTop:2}}>{onPace?"● On pace":"● Behind pace"}</div>
            {hasSupabase&&syncLabel&&<div style={{fontSize:9,color:syncColor,marginTop:2,letterSpacing:"0.08em"}}>{syncLabel}</div>}
          </div>
        </div>
        {/* Progress bar */}
        <div style={{height:3,background:"#2A2820",borderRadius:2,marginTop:12}}>
          <div style={{height:3,borderRadius:2,background:"linear-gradient(90deg,#C8A96E,#E8C98E)",width:`${Math.min((totalHrs/750)*100,100)}%`,transition:"width 0.5s"}}/>
        </div>
        {timer&&(
          <div style={{marginTop:10,background:"#1A1810",borderRadius:6,padding:"8px 12px",display:"flex",justifyContent:"space-between",alignItems:"center"}}>
            <div style={{fontSize:10,color:"#C8A96E",letterSpacing:"0.1em",textTransform:"uppercase"}}>⏱ Timer running</div>
            <div style={{fontSize:22,color:"#C8A96E",fontVariantNumeric:"tabular-nums"}}>{fmtDur(elapsed)}</div>
          </div>
        )}
      </div>

      {/* Top nav */}
      <nav className="top-nav">
        {NAV.map(n=>(
          <button key={n.id} className={`nav-item${view===n.id?" active":""}`} onClick={()=>setView(n.id)}>
            <span className="nav-icon">{n.icon}</span>
            <span>{n.label}</span>
          </button>
        ))}
      </nav>

      {/* Main content */}
      <div style={{flex:1,overflow:"hidden"}}>
        {view==="log"&&<LogView logs={logs} setLogs={setLogs} recur={recur} setRecur={setRecur} properties={properties} setProperties={setProperties} form={form} setForm={setForm} timer={timer} setTimer={setTimer} elapsed={elapsed}/>}
        {view==="recur"&&<RecurView recur={recur} setRecur={setRecur} logs={logs} setLogs={setLogs} properties={properties} setProperties={setProperties}/>}
        {view==="summary"&&<SummaryView logs={logs} totalHrs={totalHrs} totalMs={totalMs} exportCSV={exportCSV}/>}
        {view==="attest"&&<AttestView logs={logs} totalHrs={totalHrs} attest={attest} setAttest={setAttest}/>}
        {view==="account"&&<AccountView session={session} ownerUserId={ownerUserId} onSignOut={signOut} onSignOutEverywhere={signOutEverywhere}/>}
      </div>
    </div>
  );
}
