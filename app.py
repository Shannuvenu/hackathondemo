# app.py
import os
import json
import time
from datetime import datetime

import requests
import streamlit as st

# ===================== PAGE CONFIG =====================
st.set_page_config(page_title="SignCall", layout="wide")

# ===================== BACKEND URL =====================
BACKEND = os.getenv("BACKEND_URL")
if not BACKEND:
    try:
        BACKEND = st.secrets["BACKEND_URL"]
    except Exception:
        BACKEND = "http://127.0.0.1:8003"

DEFAULT_USER = "demo_user"
EMOJI_MAP = {"Yes": "👍", "No": "👎", "Hello": "✌"}

# ===================== STATE ===========================
st.session_state.setdefault("user_id", DEFAULT_USER)
st.session_state.setdefault("last_seen_ts", "")
st.session_state.setdefault("room_code", "sign-demo")
st.session_state.setdefault("teach_on", False)

# ===================== SIDEBAR =========================
with st.sidebar:
    st.markdown("## 🔐 Account")
    tabs = st.tabs(["Login", "Sign up"])

    # ---- LOGIN ----
    with tabs[0]:
        with st.form("login"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Login")
        if submitted:
            if not email or not password:
                st.error("Enter email and password.")
            else:
                try:
                    r = requests.post(
                        f"{BACKEND}/login",
                        params={"email": email, "password": password},
                        timeout=15,
                    )
                    if r.ok:
                        uid = r.json().get("user_id")
                        if uid:
                            st.session_state["user_id"] = uid
                            st.success(f"Logged in ✅ {email}")
                        else:
                            st.error("Login response missing user id.")
                    else:
                        st.error(r.text)
                except Exception as e:
                    st.error(f"Login failed: {e}")

    # ---- SIGNUP ----
    with tabs[1]:
        with st.form("signup"):
            s_email = st.text_input("Email", key="signup_email")
            s_pass = st.text_input("Password (min 6 chars)", type="password", key="signup_password")
            s_pass2 = st.text_input("Confirm password", type="password", key="signup_password2")
            s_sub = st.form_submit_button("Create account")
        if s_sub:
            if not s_email or not s_pass:
                st.error("Enter email and password.")
            elif s_pass != s_pass2:
                st.error("Passwords do not match.")
            elif len(s_pass) < 6:
                st.error("Password must be at least 6 characters.")
            else:
                try:
                    r = requests.post(
                        f"{BACKEND}/signup",
                        params={"email": s_email, "password": s_pass},
                        timeout=15,
                    )
                    if r.ok:
                        uid = r.json().get("user_id")
                        st.success("Account created 🎉")
                        st.session_state["user_id"] = uid or st.session_state.get("user_id", "demo_user")
                    else:
                        st.error(r.text)
                except Exception as e:
                    st.error(f"Signup failed: {e}")

    st.markdown("---")
    current_uid = st.session_state.get("user_id", "demo_user")
    st.caption(f"Current user: {current_uid}")
    if current_uid != "demo_user":
        if st.button("Logout"):
            st.session_state["user_id"] = "demo_user"
            st.success("Logged out.")

    st.markdown("---")
    st.markdown("## ⚙ Settings")
    user_id = st.text_input("User ID", value=st.session_state.get("user_id", "demo_user"))
    st.session_state["user_id"] = user_id

    st.markdown("## 🔊 Audio")
    play_ui_sounds = st.toggle("UI sounds (send/receive)", value=True)
    tts_enabled = st.toggle("Read incoming text (TTS)", value=False)
    tts_rate = st.slider("Voice speed", 0.5, 2.0, 1.0, 0.1)
    tts_pitch = st.slider("Voice pitch", 0.0, 2.0, 1.0, 0.1)

    autorefresh = st.toggle("Auto-refresh chat (2s)", value=True)
    translate_toggle = st.toggle("Show translations (TA + HI)", value=True)

# ===================== STYLES ==========================
st.markdown(
    """
<style>
  .msg-card{background:#111418;border:1px solid #23272f;padding:12px 14px;border-radius:14px;margin:6px 0}
  .msg-meta{font-size:12px;color:#8b97a7;margin-top:6px}
  .msg-emoji{font-size:18px;margin-left:6px}
  .msg-translate{font-size:13px;color:#cbd5e1;margin-top:6px;opacity:.95}
  .msg-you{border-left:4px solid #22c55e;padding-left:10px}
  .pill{display:inline-block;background:#1f2937;color:#e5e7eb;font-size:12px;padding:2px 8px;border-radius:999px;margin-left:8px}
  .row{display:flex;gap:12px;margin:8px 0;flex-wrap:wrap}
  button{padding:8px 12px;border-radius:10px;border:1px solid #334155;background:#111827;color:#e5e7eb;cursor:pointer}
  video, canvas{width:320px;height:240px;background:#111418;border:1px solid #23272f;border-radius:12px}
  .chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}
  .chip{background:#0f172a;border:1px solid #334155;border-radius:999px;padding:4px 10px;font-size:12px}
  /* make text inputs a bit larger for better UX (especially Teach name) */
  .stTextInput input{height:48px;font-size:18px}
</style>
""",
    unsafe_allow_html=True,
)

# ===================== LAYOUT =========================
st.title("✌ SignCall — Sign-to-Text Video Calls")
col1, col2 = st.columns([1.25, 1])

# ===================== COL1: VIDEO CALL ===============
with col1:
    st.subheader("Video Call (Multi-user)")
    st.session_state["room_code"] = st.text_input(
        "Room code (share with others to join):",
        value=st.session_state["room_code"],
    )

    _backend_js = json.dumps(BACKEND)
    _user_id_js = json.dumps(st.session_state["user_id"])
    _roomcode_js = json.dumps(st.session_state["room_code"])
    _tts_rate = float(tts_rate)
    _tts_pitch = float(tts_pitch)

    st.components.v1.html(
        f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>SignCall Room</title>
<style>
  body {{ background:#0b0f14; color:#e5e7eb; font-family:system-ui; }}
  .row{{ display:flex; gap:12px; margin:8px 0; flex-wrap:wrap }}
  .btn{{ padding:8px 12px; border-radius:10px; border:1px solid #334155; background:#111827; color:#e5e7eb; cursor:pointer }}
  .card{{ background:#111418;border:1px solid #23272f;padding:10px;border-radius:12px;margin-top:8px; width:320px }}
  video{{ width:100%; height:240px; background:#111418; border:1px solid #23272f; border-radius:12px; object-fit:cover }}
  .caption{{ font-size:16px; margin-top:6px }}
  .small{{ font-size:12px; color:#94a3b8 }}
  #remotes{{ display:flex; flex-wrap:wrap; gap:12px }}
  .chips{{ display:flex; gap:8px; flex-wrap:wrap; margin:6px 0 }}
  .chip{{ background:#0f172a;border:1px solid #334155;border-radius:999px;padding:4px 10px;font-size:12px }}
</style>
</head>
<body>
  <div class="row">
    <div class="card">
      <div><b>Local</b></div>
      <video id="localVideo" autoplay playsinline muted></video>
      <div id="localCap" class="caption small"></div>
    </div>
    <div id="remotes"></div>
  </div>

  <div class="row">
    <button class="btn" id="startCam">📷 Start Camera</button>
    <button class="btn" id="stopCam">🛑 Stop Camera</button>
    <button class="btn" id="startMic">🎤 Start STT</button>
    <button class="btn" id="stopMic">🔇 Stop STT</button>
    <button class="btn" id="startGest">🖐 Start Gestures</button>
    <button class="btn" id="stopGest">✋ Stop Gestures</button>
    <button class="btn" id="refreshLib">🔄 Refresh gestures</button>
  </div>

  <div id="status" class="small">Status: idle</div>
  <div class="small" style="margin-top:6px">Custom gestures:</div>
  <div id="customList" class="chips"></div>

  <!-- PeerJS -->
  <script src="https://unpkg.com/peerjs@1.5.2/dist/peerjs.min.js"></script>

  <!-- Mediapipe Hands -->
  <script src="https://cdn.jsdelivr.net/npm/@mediapipe/hands/hands.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils/camera_utils.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/@mediapipe/drawing_utils/drawing_utils.js"></script>

  <script>
  const BACKEND  = {_backend_js};
  const USER_ID  = {_user_id_js};
  const ROOMCODE = {_roomcode_js};
  const TTS_RATE = {_tts_rate};
  const TTS_PITCH= {_tts_pitch};

  // Derive websocket URL from BACKEND (no template braces to confuse Python)
  const _bURL = new URL(BACKEND);
  const _wsScheme = (_bURL.protocol === 'https:') ? 'wss:' : 'ws:';
  const _wsHost   = _bURL.host;
  function wsRoomURL(code) {{
    return _wsScheme + '//' + _wsHost + '/ws/room/' + encodeURIComponent(code);
  }}

  const statusEl   = document.getElementById('status');
  const localVideo = document.getElementById('localVideo');
  const localCap   = document.getElementById('localCap');
  const remotesDiv = document.getElementById('remotes');
  const customList = document.getElementById('customList');

  let localStream = null;
  let peer = null;
  let myPeerId = null;
  let ws = null;

  // pid -> {{ call, data, videoEl, capEl, transEl }}
  const peers = {{}};

  // ===== Custom gesture library =====
  // Each entry: {{ name: string, vecs: [Float32Array] }}
  let GESTURE_LIB = [];
  // runtime window buffer (36 frames of 63-dim vectors)
  let WIN = [];
  let customOn = false;
  let cooldownUntil = 0;

  function setStatus(t) {{ statusEl.textContent = "Status: " + t; }}

  async function apiSave(content, emoji="") {{
    try {{
      await fetch(${{BACKEND}}/message?user_id=${{encodeURIComponent(USER_ID)}}&content=${{encodeURIComponent(content)}}&emoji=${{encodeURIComponent(emoji)}}&language=en, {{ method: 'POST' }});
    }} catch (e) {{ console.error(e); }}
  }}

  async function translate(text, lang) {{
    try {{
      const r = await fetch(${{BACKEND}}/translate?text=${{encodeURIComponent(text)}}&lang=${{lang}});
      if (!r.ok) return "";
      const j = await r.json();
      return j.translated || "";
    }} catch(e){{ return ""; }}
  }}

  function speak(text) {{
    try {{
      const pick = localStorage.getItem("signcall_voice");
      const u = new SpeechSynthesisUtterance(text);
      u.lang = "en-US";
      u.rate = TTS_RATE;
      u.pitch= TTS_PITCH;
      const vs = window.speechSynthesis.getVoices();
      const found = vs.find(v => v.name === pick);
      if (found) u.voice = found;
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(u);
    }} catch(e){{}}
  }}

  function ensureRemoteSlot(pid) {{
    if (peers[pid] && peers[pid].videoEl) return peers[pid];
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = `<div><b>${{pid}}</b></div>
                      <video autoplay playsinline></video>
                      <div class="caption" data-cap></div>
                      <div class="caption small" data-trans></div>`;
    remotesDiv.appendChild(card);
    const videoEl = card.querySelector('video');
    const capEl   = card.querySelector('[data-cap]');
    const transEl = card.querySelector('[data-trans]');
    peers[pid] = Object.assign(peers[pid] || {{}}, {{ videoEl, capEl, transEl }});
    return peers[pid];
  }}

  function broadcastCaption(text, emoji="") {{
    localCap.innerText = text + (emoji ? " " + emoji : "");
    apiSave(text, emoji);
    Object.values(peers).forEach(p => {{
      if (p.data && p.data.open) p.data.send({{ type:"caption", text, emoji }});
    }});
  }}

  function handleIncomingData(fromPid, msg) {{
    if (!msg || msg.type !== "caption") return;
    const p = ensureRemoteSlot(fromPid);
    const line = (msg.text || "") + (msg.emoji ? " " + msg.emoji : "");
    p.capEl.innerText = line;
    (async () => {{
      const ta = await translate(msg.text || "", "ta");
      const hi = await translate(msg.text || "", "hi");
      p.transEl.innerHTML = TA: ${{ta}}<br/>HI: ${{hi}};
    }})();
    speak(msg.text || "");
  }}

  // ---- PeerJS setup ----
  async function initPeer() {{
    return new Promise((resolve) => {{
      const useCloud = {{ host:'peerjs.com', secure:true, port:443 }};
      peer = new Peer(null, useCloud);
      peer.on('open', (id) => {{
        myPeerId = id;
        setStatus("Peer ready (id: " + id + ") Room: " + ROOMCODE);
        resolve(peer);

        // incoming media
        peer.on('call', (incomingCall) => {{
          incomingCall.answer(localStream);
          incomingCall.on('stream', (remote) => {{
            const pid = incomingCall.peer;
            const slot = ensureRemoteSlot(pid);
            slot.videoEl.srcObject = remote;
          }});
          const pid = incomingCall.peer;
          peers[pid] = Object.assign(peers[pid] || {{}}, {{ call: incomingCall }});
        }});

        // incoming data
        peer.on('connection', (conn) => {{
          const pid = conn.peer;
          peers[pid] = Object.assign(peers[pid] || {{}}, {{ data: conn }});
          conn.on('data', (msg) => handleIncomingData(pid, msg));
        }});

        joinRoomWS();
      }});
    }});
  }}

  // ---- WS signalling ----
  function joinRoomWS() {{
    ws = new WebSocket(wsRoomURL(ROOMCODE));
    ws.onopen = () => {{
      ws.send(JSON.stringify({{ type:"hello", peerId: myPeerId, userId: USER_ID }}));
    }};
    ws.onmessage = (ev) => {{
      const m = JSON.parse(ev.data || '{{}}');
      if (m.type === 'peers' && Array.isArray(m.peers)) {{
        m.peers.forEach(pid => {{
          if (!pid || pid === myPeerId) return;
          if (peers[pid] && (peers[pid].call || peers[pid].data)) return;

          const outCall = peer.call(pid, localStream);
          outCall.on('stream', (remote) => {{
            const slot = ensureRemoteSlot(pid);
            slot.videoEl.srcObject = remote;
          }});
          const dconn = peer.connect(pid);
          dconn.on('data', (msg) => handleIncomingData(pid, msg));
          peers[pid] = Object.assign(peers[pid] || {{}}, {{ call: outCall, data: dconn }});
        }});
      }}
    }};
    ws.onclose = () => setStatus("Room socket closed");
  }}

  // ---- Buttons ----
  document.getElementById('startCam').onclick = async () => {{
    localStream = await navigator.mediaDevices.getUserMedia({{ video: true, audio: true }});
    localVideo.srcObject = localStream;
    await initPeer();
    setStatus("Camera ON");
  }};
  document.getElementById('stopCam').onclick = () => {{
    Object.values(peers).forEach(p => {{
      try {{ p.call && p.call.close(); }} catch(e){{}}
      try {{ p.data && p.data.close(); }} catch(e){{}}
    }});
    if (localStream) {{
      localStream.getTracks().forEach(t => t.stop());
      localStream = null;
      localVideo.srcObject = null;
    }}
    try {{ ws && ws.close(); }} catch(e){{}}
    setStatus("Camera OFF");
  }};

  // ---- Web Speech (STT) ----
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recog = null;
  document.getElementById('startMic').onclick = () => {{
    if (!SR) {{ setStatus("Web Speech not supported"); return; }}
    recog = new SR();
    recog.lang = "en-US";
    recog.interimResults = true;
    recog.continuous = true;
    recog.onresult = (ev) => {{
      for (let i=ev.resultIndex; i<ev.results.length; i++) {{
        const res = ev.results[i];
        const txt = res[0].transcript.trim();
        if (txt && res.isFinal) broadcastCaption(txt, "");
      }}
    }};
    recog.start();
    setStatus("STT ON");
  }};
  document.getElementById('stopMic').onclick = () => {{
    if (recog) try {{ recog.stop(); }} catch(e){{}}
    setStatus("STT OFF");
  }};

  // ---- Custom gesture library loading & UI ----
  function renderGestureChips() {{
    customList.innerHTML = "";
    if (!GESTURE_LIB.length) {{
      const div = document.createElement('div');
      div.className = 'chip';
      div.textContent = "None yet";
      customList.appendChild(div);
      return;
    }}
    const names = [...new Set(GESTURE_LIB.map(g => g.name))];
    names.forEach(n => {{
      const c = document.createElement('div');
      c.className = 'chip';
      c.textContent = n;
      customList.appendChild(c);
    }});
  }}

  function meanVec(frames) {{
    // frames: array of 63-length arrays
    const d = 63;
    const out = new Float32Array(d);
    for (let i=0;i<frames.length;i++) {{
      const f = frames[i];
      for (let j=0;j<d;j++) out[j] += f[j];
    }}
    const inv = 1 / Math.max(frames.length, 1);
    for (let j=0;j<d;j++) out[j] *= inv;
    return out;
  }}

  function cosine(a, b) {{
    let dot=0, na=0, nb=0;
    for (let i=0;i<a.length;i++) {{
      dot += a[i]*b[i];
      na += a[i]*a[i];
      nb += b[i]*b[i];
    }}
    return dot / (Math.sqrt(na)*Math.sqrt(nb) + 1e-9);
  }}

  async function loadGestureLibrary() {{
    try {{
      const url = ${{BACKEND}}/custom_gesture/samples?user_id=${{encodeURIComponent(USER_ID)}};
      const r = await fetch(url);
      if (!r.ok) throw new Error("fetch failed");
      const rows = await r.json(); // each: {{name, seq_json}}
      const lib = [];
      for (const row of rows) {{
        const name = row.name || "custom";
        const seq = (row.seq_json && row.seq_json.frames) || [];
        const frames = seq.map(fr => Float32Array.from(fr)); // 36x63 flattened
        const v = meanVec(frames);
        lib.push({{ name, vecs: [v] }});
      }}
      // merge by name
      const byName = {{}};
      for (const g of lib) {{
        if (!byName[g.name]) byName[g.name] = {{ name:g.name, vecs:[] }};
        byName[g.name].vecs.push(...g.vecs);
      }}
      GESTURE_LIB = Object.values(byName);
      renderGestureChips();
      customOn = GESTURE_LIB.length > 0;
      setStatus(customOn ? "Gestures ON (custom loaded)" : "Gestures ON");
    }} catch(e) {{
      console.warn("loadGestureLibrary failed", e);
      GESTURE_LIB = [];
      renderGestureChips();
    }}
  }}

  document.getElementById('refreshLib').onclick = () => loadGestureLibrary();

  // ---- MediaPipe Hands (quick + custom) ----
  let camera = null;
  const videoGhost = document.createElement('video');
  const hands = new Hands({{ locateFile: (f) => https://cdn.jsdelivr.net/npm/@mediapipe/hands/${{f}} }});
  hands.setOptions({{
    maxNumHands: 1, modelComplexity: 1, minDetectionConfidence: 0.7, minTrackingConfidence: 0.7
  }});

  function normalize(points) {{
    // points: 21 landmarks [{{x,y,z}}...]
    const base = points[0];
    const shifted = points.map(p => [p.x - base.x, p.y - base.y, p.z - base.z]);
    let m=0;
    for (let i=1;i<shifted.length;i++) {{
      const d = Math.hypot(shifted[i][0], shifted[i][1], shifted[i][2]);
      m += d;
    }}
    m = Math.max(m / Math.max(shifted.length-1,1), 1e-6);
    return shifted.map(p => [p[0]/m, p[1]/m, p[2]/m]); // 21x3
  }}

  function flatten63(n21x3) {{
    const out = new Float32Array(63);
    let k=0; for (let i=0;i<21;i++) {{ out[k++]=n21x3[i][0]; out[k++]=n21x3[i][1]; out[k++]=n21x3[i][2]; }}
    return out;
  }}

  function tryCustomRecognition() {{
    if (!customOn) return;
    if (Date.now() < cooldownUntil) return;
    if (WIN.length < 36) return;
    // make current mean vector
    const cur = meanVec(WIN);
    // find nearest gesture by max cosine over all samples
    let bestName = "";
    let bestScore = -1;
    for (const g of GESTURE_LIB) {{
      for (const v of g.vecs) {{
        const s = cosine(cur, v);
        if (s > bestScore) {{ bestScore = s; bestName = g.name; }}
      }}
    }}
    // threshold to avoid noise
    if (bestScore >= 0.92) {{
      broadcastCaption(bestName, "🖐");
      cooldownUntil = Date.now() + 1500; // 1.5s cooldown
      WIN = []; // reset window so it doesn’t spam
    }}
  }}

  hands.onResults((results) => {{
    if (!results.multiHandLandmarks || results.multiHandLandmarks.length===0) return;

    // ===== Hard-coded quick signs =====
    const lm = results.multiHandLandmarks[0];
    const isExt = (tip,pip)=> lm[tip].y < lm[pip].y;
    const isFold= (tip,pip)=> lm[tip].y > lm[pip].y;

    const idxExt  = isExt(8,6);
    const midExt  = isExt(12,10);
    const ringF   = isFold(16,14);
    const pinkF   = isFold(20,18);
    const thumbUp   = isExt(4,2) && ringF && pinkF && !idxExt && !midExt;
    const thumbDown = isFold(4,2) && ringF && pinkF && !idxExt && !midExt;
    const dx = Math.abs(lm[8].x - lm[12].x);
    const vSign = idxExt && midExt && ringF && pinkF && dx > 0.05;

    if (thumbUp)      {{ broadcastCaption("Yes", "👍"); return; }}
    if (thumbDown)    {{ broadcastCaption("No", "👎"); return; }}
    if (vSign)        {{ broadcastCaption("Hello", "✌"); return; }}

    // ===== Custom window-building =====
    const n = normalize(lm);
    const f63 = flatten63(n);
    WIN.push(Array.from(f63));
    if (WIN.length > 36) WIN.shift();

    tryCustomRecognition();
  }});

  document.getElementById('startGest').onclick = async () => {{
    if (!localStream) {{ setStatus("Start camera first."); return; }}
    await loadGestureLibrary(); // load samples when starting gestures
    videoGhost.srcObject = localStream;
    videoGhost.play();
    camera = new window.Camera(videoGhost, {{
      onFrame: async () => {{ await hands.send({{ image: videoGhost }}); }},
      width: 320, height: 240
    }});
    camera.start();
    setStatus("Gestures ON");
  }};
  document.getElementById('stopGest').onclick = () => {{
    if (camera) camera.stop();
    customOn = false;
    WIN = [];
    setStatus("Gestures OFF");
  }};
  </script>
</body>
</html>
""",
        height=900,
        scrolling=True,
    )

# ===================== Teach a custom sign =====================
with st.expander("🧪 Teach a custom sign (Personal Dictionary)", expanded=False):
    # Bigger input by CSS above; keep text_input (single-line)
    teach_name = st.text_input("Sign name (e.g., Amma, Bus stop, OK?)", key="teach_name")
    teach_reps = st.number_input("Samples to record", 5, 20, 5, key="teach_reps")
    st.caption(
        "Click *Start teach* then perform the sign; it will capture ~1.2s windows repeatedly until the target sample count is reached."
    )

    colA, colB = st.columns([1, 1])
    start_clicked = colA.button("Start teach", use_container_width=True)
    stop_clicked = colB.button("Stop teach", use_container_width=True)

    if start_clicked and teach_name.strip():
        st.session_state["teach_on"] = True
    if stop_clicked:
        st.session_state["teach_on"] = False

    if st.session_state.get("teach_on"):
        uid_js = json.dumps(st.session_state["user_id"])
        name_js = json.dumps(teach_name.strip())
        reps_js = int(teach_reps)
        backend_js = json.dumps(BACKEND)

        st.components.v1.html(
            f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  <style>
    body {{ background:#0b0f14; color:#e5e7eb; font-family:system-ui; margin:0; padding:8px }}
    .wrap {{ border:1px solid #23272f; border-radius:10px; padding:10px; background:#111418 }}
    .row {{ display:flex; gap:12px; align-items:flex-start }}
    video {{ width:320px; height:240px; background:#0b0f14; border:1px solid #23272f; border-radius:10px }}
    .help {{ font-size:14px; color:#cbd5e1; line-height:1.5 }}
    .stat {{ margin-top:8px; font-size:14px; color:#cbd5e1 }}
    .ok {{ color:#22c55e }}
    .warn {{ color:#eab308 }}
    .err {{ color:#ef4444 }}
  </style>

  <!-- MediaPipe Hands + utils -->
  <script src="https://cdn.jsdelivr.net/npm/@mediapipe/hands/hands.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils/camera_utils.js"></script>
</head>
<body>
  <div class="wrap">
    <div class="row">
      <div>
        <video id="cam" autoplay playsinline muted></video>
      </div>
      <div class="help">
        <div><b>How to record:</b></div>
        <ol>
          <li>Bring your hand into the camera frame.</li>
          <li>Hold your <b>{teach_name}</b> sign steady for ~1–2 seconds.</li>
          <li>We will capture and save {reps_js} samples automatically.</li>
        </ol>
        <div id="msg" class="warn">Preparing camera & model…</div>
      </div>
    </div>
    <div id="teachStat" class="stat">Recording samples… 0/{reps_js}</div>
  </div>

<script>
  const BACKEND = {backend_js};
  const USER_ID = {uid_js};
  const NAME    = {name_js};
  const TARGET  = {reps_js};

  let teaching = true;
  let count = 0;
  let frames = [];
  let camera = null;

  function setMsg(t, cls='help') {{
    const e = document.getElementById('msg');
    e.textContent = t; e.className = cls;
  }}
  function setStat(done, total) {{
    document.getElementById('teachStat').textContent = Recording samples… ${{done}}/${{total}};
  }}

  function normalize(pts) {{
    const base = pts[0];
    const shifted = pts.map(p => [p[0]-base[0], p[1]-base[1], p[2]-base[2]]);
    let m=0; for (let i=1;i<shifted.length;i++) {{ const d = Math.hypot(shifted[i][0], shifted[i][1], shifted[i][2]); m += d; }}
    m = Math.max(m/(shifted.length-1), 1e-6);
    return shifted.map(p => [p[0]/m, p[1]/m, p[2]/m]);
  }}

  async function saveSample(sampleIdx, seqFrames) {{
    try {{
      const r = await fetch(${{BACKEND}}/custom_gesture/save?user_id=${{encodeURIComponent(USER_ID)}}&name=${{encodeURIComponent(NAME)}}&sample_idx=${{sampleIdx}}, {{
        method:"POST", headers:{{"Content-Type":"application/json"}},
        body: JSON.stringify({{ frames: seqFrames }})
      }});
      return r.ok;
    }} catch(e) {{ return false; }}
  }}

  const hands = new Hands({{ locateFile: f => https://cdn.jsdelivr.net/npm/@mediapipe/hands/${{f}} }});
  hands.setOptions({{ maxNumHands:1, modelComplexity:1, minDetectionConfidence:0.7, minTrackingConfidence:0.7 }});

  hands.onResults(async (res) => {{
    if (!teaching) return;
    if (!res.multiHandLandmarks || !res.multiHandLandmarks.length) {{
      setMsg("Show your hand to the camera and hold the sign steady…", "warn");
      return;
    }}
    const lm = res.multiHandLandmarks[0];
    const pts = lm.map(p => [p.x, p.y, p.z]);
    const n = normalize(pts);
    frames.push(n.flat());

    if (frames.length >= 36) {{
      const seq = frames.slice(0,36);
      frames = [];
      count++;
      setStat(count, TARGET);
      setMsg(Captured sample #${{count}} ✓, "ok");

      const ok = await saveSample(count, seq);
      if (!ok) setMsg("Save failed (check backend URL)", "err");

      if (count >= TARGET) {{
        setMsg("Done! You can close this section.", "ok");
        teaching = false;
        try {{ camera.stop(); }} catch(_e) {{}}
        const v = document.getElementById('cam');
        try {{ v.srcObject && v.srcObject.getTracks().forEach(t => t.stop()); }} catch(_e) {{}}
      }}
    }}
  }});

  (async () => {{
    try {{
      const v = document.getElementById('cam');
      const stream = await navigator.mediaDevices.getUserMedia({{video: {{ width: 320, height: 240 }}}});
      v.srcObject = stream; await v.play();
      camera = new Camera(v, {{
        onFrame: async () => {{ await hands.send({{ image: v }}); }},
        width: 320, height: 240
      }});
      await camera.start();
      setMsg("Camera ready. Hold your sign steady to record…", "ok");
    }} catch (e) {{
      setMsg("Camera permission denied. Allow camera and try again.", "err");
    }}
  }})();
</script>
</body>
</html>
            """,
            height=360,
            scrolling=False,
        )
    elif st.session_state.get("teach_on") is False:
        st.info("Teaching stopped.")

# ===================== COL2: CHAT =====================
with col2:
    st.subheader("Chat")
    msg = st.text_input("Type your message", placeholder="Say Hello / Yes / No …")

    send_col, load_col, clear_col = st.columns([1, 1, 1])

    def play_ui_sound(kind: str):
        url = (
            "https://cdn.jsdelivr.net/gh/napthedev/tones@main/click.mp3"
            if kind == "send"
            else "https://cdn.jsdelivr.net/gh/napthedev/tones@main/notify.mp3"
        )
        st.components.v1.html(
            f'<audio autoplay style="display:none"><source src="{url}" type="audio/mpeg"></audio>',
            height=0,
        )

    if send_col.button("Send", use_container_width=True):
        final_emoji = EMOJI_MAP.get((msg or "").strip().title(), "")
        try:
            res = requests.post(
                f"{BACKEND}/message",
                params={
                    "user_id": st.session_state["user_id"],
                    "content": (msg or "").strip(),
                    "emoji": final_emoji,
                    "language": "en",
                },
                timeout=10,
            )
            if res.ok:
                st.success("Message sent!")
                if play_ui_sounds:
                    play_ui_sound("send")
        except Exception as e:
            st.error(f"Failed: {e}")

    if load_col.button("Reload", use_container_width=True):
        st.session_state["_force_reload"] = True

    if clear_col.button("Clear History", use_container_width=True):
        try:
            res = requests.delete(f"{BACKEND}/history/{st.session_state['user_id']}", timeout=10)
            if res.ok:
                st.success("Chat history cleared!")
        except Exception as e:
            st.error(f"Failed: {e}")

    st.markdown("### History")
    history_box = st.container()

# ===================== HELPERS ========================
def fetch_history(uid: str):
    try:
        r = requests.get(f"{BACKEND}/history/{uid}", timeout=10)
        return r.json() if r.ok else []
    except Exception:
        return []

def translate_line(text: str, lang: str):
    try:
        r = requests.get(f"{BACKEND}/translate", params={"text": text, "lang": lang}, timeout=10)
        if r.ok:
            return r.json().get("translated", "")
    except Exception:
        pass
    return ""

def render_messages(items):
    if not items:
        st.info("No messages yet. Start by sending one.")
        return
    items = sorted(items, key=lambda x: x.get("timestamp", ""))
    for row in items:
        content = (row.get("content") or "").strip()
        emoji = row.get("emoji", "")
        ts = row.get("timestamp", "")
        try:
            pretty_ts = datetime.fromisoformat(ts.replace("Z", "")).strftime("%d %b %Y • %I:%M %p")
        except Exception:
            pretty_ts = ts

        st.markdown(
            f"""
            <div class="msg-card msg-you">
              <div><strong>You</strong> <span class="pill">en</span></div>
              <div style="margin-top:6px">{content} <span class="msg-emoji">{emoji}</span></div>
              <div class="msg-meta">{pretty_ts}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if translate_toggle and content:
            ta = translate_line(content, "ta")
            hi = translate_line(content, "hi")
            if ta or hi:
                st.markdown(
                    f"""<div class="msg-translate">
                    <div>🇮🇳 TA: {ta}</div>
                    <div>🇮🇳 HI: {hi}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )

items = fetch_history(st.session_state["user_id"])
with history_box:
    render_messages(items)

if items:
    newest_ts = max(x.get("timestamp", "") for x in items)
    if newest_ts and newest_ts != st.session_state["last_seen_ts"]:
        if st.session_state["last_seen_ts"] and play_ui_sounds:
            play_ui_sound("recv")
        st.session_state["last_seen_ts"] = newest_ts

if st.session_state.get("_force_reload"):
    st.session_state["_force_reload"] = False
    st.rerun()

if autorefresh:
    time.sleep(2)
    st.rerun()