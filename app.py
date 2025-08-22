import time
import requests
import streamlit as st
from datetime import datetime
import json

# ===================== PAGE CONFIG =====================
st.set_page_config(page_title="SignCall", layout="wide")

# ===================== CONFIG ==========================
BACKEND = "http://127.0.0.1:8000"
DEFAULT_USER = "demo_user"  # replace with Supabase Auth uid after login
EMOJI_MAP = {"Yes": "👍", "No": "👎", "Hello": "✌"}

# ===================== STATE ===========================
if "user_id" not in st.session_state:
    st.session_state["user_id"] = DEFAULT_USER
if "last_seen_ts" not in st.session_state:
    st.session_state["last_seen_ts"] = ""
if "room_code" not in st.session_state:
    st.session_state["room_code"] = "sign-demo"  # any default

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
    st.caption(f"Current user: `{current_uid}`")
    if current_uid != "demo_user":
        if st.button("Logout"):
            st.session_state["user_id"] = "demo_user"
            st.success("Logged out.")

    st.markdown("---")
    st.markdown("## ⚙️ Settings")
    user_id = st.text_input("User ID", value=st.session_state.get("user_id", "demo_user"))
    st.session_state["user_id"] = user_id

    st.markdown("## 🔊 Audio")
    play_ui_sounds = st.toggle("UI sounds (send/receive)", value=True)
    tts_enabled = st.toggle("Read incoming text (TTS)", value=False)
    tts_rate = st.slider("Voice speed", min_value=0.5, max_value=2.0, value=1.0, step=0.1)
    tts_pitch = st.slider("Voice pitch", min_value=0.0, max_value=2.0, value=1.0, step=0.1)

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
      .msg-peer{border-left:4px solid #3b82f6;padding-left:10px}
      .pill{display:inline-block;background:#1f2937;color:#e5e7eb;font-size:12px;padding:2px 8px;border-radius:999px;margin-left:8px}
      .primary{background:#2563eb}
      .danger{background:#ef4444}
      .row{display:flex;gap:12px;margin:8px 0;flex-wrap:wrap}
      button{padding:8px 12px;border-radius:10px;border:1px solid #334155;background:#111827;color:#e5e7eb;cursor:pointer}
      video, canvas{width:320px;height:240px;background:#111418;border:1px solid #23272f;border-radius:12px}
    </style>
    """,
    unsafe_allow_html=True,
)

# ===================== LAYOUT =========================
st.title("✌️ SignCall — Sign-to-Text Video Calls")
col1, col2 = st.columns([1.2, 1])

# ===================== COL1: MULTI-USER CALL =========
with col1:
    st.subheader("Video Call (Multi-user)")
    st.session_state["room_code"] = st.text_input(
        "Room code (share with others to join):",
        value=st.session_state["room_code"]
    )

    # Main embedded UI (PeerJS + WS + WebSpeech + MediaPipe)
   

_backend_js  = json.dumps(BACKEND)
_user_id_js  = json.dumps(st.session_state["user_id"])
_roomcode_js = json.dumps(st.session_state["room_code"])

st.components.v1.html(f"""
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
    <button class="btn" id="startGest">🖐️ Start Gestures</button>
    <button class="btn" id="stopGest">✋ Stop Gestures</button>
  </div>

  <div id="status" class="small">Status: idle</div>

  <!-- PeerJS -->
  <script src="https://unpkg.com/peerjs@1.5.2/dist/peerjs.min.js"></script>

  <!-- Mediapipe Hands -->
  <script src="https://cdn.jsdelivr.net/npm/@mediapipe/hands/hands.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils/camera_utils.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/@mediapipe/drawing_utils/drawing_utils.js"></script>

  <!-- TFJS (optional future models) -->
  <script src="https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@4.20.0/dist/tf.min.js"></script>

  <script>
  // ---- values injected from Streamlit ----
  const BACKEND  = {_backend_js};
  const USER_ID  = {_user_id_js};
  const ROOMCODE = {_roomcode_js};

  // derive websocket URL from BACKEND
  const _bURL = new URL(BACKEND);
  const _wsScheme = (_bURL.protocol === 'https:') ? 'wss:' : 'ws:';
  const _wsHost   = _bURL.host;
  function wsRoomURL(code) {{ return `${{_wsScheme}}//${{_wsHost}}/ws/room/${{encodeURIComponent(code)}}`; }}

  const statusEl   = document.getElementById('status');
  const localVideo = document.getElementById('localVideo');
  const localCap   = document.getElementById('localCap');
  const remotesDiv = document.getElementById('remotes');

  let localStream = null;
  let peer = null;
  let myPeerId = null;
  let ws = null;

  // pid -> {{ "call": RTCPeerConnection, "data": DataConnection, "videoEl": HTMLVideoElement, "capEl": HTMLElement, "transEl": HTMLElement }}
  const peers = {{}};

  function setStatus(t) {{ statusEl.textContent = "Status: " + t; }}

  async function apiSave(content, emoji="") {{
    try {{
      await fetch(`${{BACKEND}}/message?user_id=${{encodeURIComponent(USER_ID)}}&content=${{encodeURIComponent(content)}}&emoji=${{encodeURIComponent(emoji)}}&language=en`, {{ method: 'POST' }});
    }} catch (e) {{ console.error(e); }}
  }}

  async function translate(text, lang) {{
    try {{
      const r = await fetch(`${{BACKEND}}/translate?text=${{encodeURIComponent(text)}}&lang=${{lang}}`);
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
      u.rate = {float(tts_rate)};
      u.pitch = {float(tts_pitch)};
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
    peers[pid] = Object.assign(peers[pid] || {{}}, {{ "videoEl": videoEl, "capEl": capEl, "transEl": transEl }});
    return peers[pid];
  }}

  function broadcastCaption(text, emoji="") {{
    localCap.innerText = text + (emoji ? " " + emoji : "");
    apiSave(text, emoji);
    Object.values(peers).forEach(p => {{
      if (p.data && p.data.open) p.data.send({{ "type":"caption", "text": text, "emoji": emoji }});
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
      p.transEl.innerHTML = `TA: ${{ta}}<br/>HI: ${{hi}}`;
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
          peers[pid] = Object.assign(peers[pid] || {{}}, {{ "call": incomingCall }});
        }});

        // incoming data
        peer.on('connection', (conn) => {{
          const pid = conn.peer;
          peers[pid] = Object.assign(peers[pid] || {{}}, {{ "data": conn }});
          conn.on('data', (msg) => handleIncomingData(pid, msg));
        }});

        joinRoomWS();
      }});
    }});
  }}

  // ---- WS signalling (room membership -> peer ids) ----
  function joinRoomWS() {{
    ws = new WebSocket(wsRoomURL(ROOMCODE));
    ws.onopen = () => {{
      ws.send(JSON.stringify({{ "type":"hello", "peerId": myPeerId, "userId": USER_ID }}));
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

          peers[pid] = Object.assign(peers[pid] || {{}}, {{ "call": outCall, "data": dconn }});
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

  // ---- MediaPipe Hands (👍 / 👎 / ✌) ----
  let camera = null;
  const videoGhost = document.createElement('video');
  const hands = new Hands({{ locateFile: (f) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${{f}}` }});
  hands.setOptions({{
    maxNumHands: 1, modelComplexity: 1, minDetectionConfidence: 0.7, minTrackingConfidence: 0.7
  }});
  hands.onResults((results) => {{
    if (!results.multiHandLandmarks || results.multiHandLandmarks.length===0) return;
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

    if (thumbUp)      broadcastCaption("Yes", "👍");
    else if (thumbDown) broadcastCaption("No", "👎");
    else if (vSign)     broadcastCaption("Hello", "✌");
  }});

  document.getElementById('startGest').onclick = async () => {{
    if (!localStream) {{ setStatus("Start camera first."); return; }}
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
    setStatus("Gestures OFF");
  }};
  </script>
</body>
</html>
""", height=820, scrolling=True)


    # ===== Personal Dictionary: Teach a custom sign =====
with st.expander("🧪 Teach a custom sign (Personal Dictionary)"):
        teach_name = st.text_input("Sign name (e.g., Amma, Bus stop, OK?)", key="teach_name")
        teach_reps = st.number_input("Samples to record", 5, 20, 8)
        st.caption("Click [Start teach] then perform the sign; it will capture ~1.2s windows repeatedly.")
        teach_start = st.button("Start teach")
        teach_stop = st.button("Stop teach")

        if teach_start and teach_name:
            st.session_state["teach_on"] = True
        if teach_stop:
            st.session_state["teach_on"] = False

        if st.session_state.get("teach_on"):
            st.components.v1.html(f"""
            <div style="padding:8px;background:#111418;border:1px solid #23272f;border-radius:10px;margin-top:8px">
              <div id="teachStat" style="color:#cbd5e1;font-size:14px">Recording samples… 0/{teach_reps}</div>
            </div>
            <script>
              (function(){{
                const USER_ID = {st.session_state["user_id"]!r};
                const NAME = {teach_name!r};
                const TARGET = {int(teach_reps)};
                let count = 0;
                let frames = [];
                let teaching = true;

                async function getStream(){{ try {{ return await navigator.mediaDevices.getUserMedia({{video:true}}); }} catch(e){{ return null; }} }}
                function normalize(pts){{
                  const base = pts[0];
                  const shifted = pts.map(p => [p[0]-base[0], p[1]-base[1], p[2]-base[2]]);
                  let m=0; for (let i=1;i<shifted.length;i++) {{ const d = Math.hypot(shifted[i][0], shifted[i][1], shifted[i][2]); m += d; }}
                  m = Math.max(m/(shifted.length-1), 1e-6);
                  return shifted.map(p => [p[0]/m, p[1]/m, p[2]/m]);
                }}

                const hands = new Hands({{ locateFile: f => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${{f}}` }});
                hands.setOptions({{ maxNumHands: 1, modelComplexity: 1, minDetectionConfidence: 0.7, minTrackingConfidence: 0.7 }});

                const v = document.createElement('video'); v.style.display='none'; document.body.appendChild(v);

                hands.onResults((res) => {{
                  if (!teaching || !res.multiHandLandmarks || !res.multiHandLandmarks.length) return;
                  const lm = res.multiHandLandmarks[0];
                  const pts = lm.map(p => [p.x, p.y, p.z]);
                  const n = normalize(pts);
                  frames.push(n.flat().flat());
                  if (frames.length >= 36) {{
                    const seq = frames.slice(0,36);
                    frames = [];
                    count++;
                    document.getElementById('teachStat').innerText = `Recording samples… ${{count}}/${{TARGET}}`;
                    fetch("{BACKEND}/custom_gesture/save?user_id="+encodeURIComponent(USER_ID)+"&name="+encodeURIComponent(NAME)+"&sample_idx="+count, {{
                      method:"POST", headers:{{"Content-Type":"application/json"}}, body: JSON.stringify({{frames: seq}})
                    }});
                    if (count >= TARGET) teaching = false;
                  }}
                }});

                (async ()=>{{
                  const s = await getStream();
                  if (!s) return;
                  v.srcObject = s; await v.play();
                  const cam = new window.Camera(v, {{ onFrame: async()=>{{ await hands.send({{image:v}}); }}, width:320,height:240 }});
                  cam.start();
                  setTimeout(()=>{{ teaching=false; cam.stop(); s.getTracks().forEach(t=>t.stop()); }}, 120000);
                }})();
              }})();
            </script>
            """, height=90)

# ===================== COL2: CHAT ======================
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

    def tts_say(text: str):
        st.components.v1.html(
            f"""
            <script>
              (function(){{
                const text = {text!r};
                const rate = {float(tts_rate)};
                const pitch = {float(tts_pitch)};
                const pick = localStorage.getItem("signcall_voice");
                const u = new SpeechSynthesisUtterance(text);
                u.lang = "en-US"; u.rate = rate; u.pitch = pitch;
                const vs = window.speechSynthesis.getVoices();
                const found = vs.find(v => v.name === pick);
                if (found) u.voice = found;
                window.speechSynthesis.cancel();
                window.speechSynthesis.speak(u);
              }})();
            </script>
            """,
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

        who = "You"  # placeholder until we mark sender
        klass = "msg-you"

        st.markdown(
            f"""
            <div class="msg-card {klass}">
              <div><strong>{who}</strong> <span class="pill">en</span></div>
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

        if tts_enabled and content:
            tts_say(content)

# ===================== RENDER + AUTO REFRESH =========
items = fetch_history(st.session_state["user_id"])
with history_box:
    render_messages(items)

# notify on new
if items:
    newest_ts = max(x.get("timestamp", "") for x in items)
    if newest_ts and newest_ts != st.session_state["last_seen_ts"]:
        if st.session_state["last_seen_ts"] and play_ui_sounds:
            play_ui_sound("recv")
        st.session_state["last_seen_ts"] = newest_ts

# manual reload
if st.session_state.get("_force_reload"):
    st.session_state["_force_reload"] = False
    st.rerun()

# soft auto-refresh
if autorefresh:
    time.sleep(2)
    st.rerun()
