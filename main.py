# main.py
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from dotenv import load_dotenv
from typing import Dict, Any, List
from supabase import create_client
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List
import requests
import os

# ----------------- Load env & init Supabase -----------------
load_dotenv()  # expects SUPABASE_URL and SUPABASE_KEY in .env

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://htwvjbsqpuozqbnszsad.supabase.co")
SUPABASE_KEY = os.getenv(
    "SUPABASE_KEY",
    # fallback for local dev ONLY; do not commit a real service key in prod
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh0d3ZqYnNxcHVvenFibnN6c2FkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTU2MjA4MjYsImV4cCI6MjA3MTE5NjgyNn0.5M77PWqMahvbBZJdCXcytgEwBaXeju5OaFt02FHYshY"
)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ----------------- App & CORS -----------------
app = FastAPI(title="SignCall Backend", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Known sign → emoji mapping
EMOJI_MAP = {"yes": "👍", "no": "👎", "hello": "✌"}

# ----------------- Healthcheck -----------------
@app.get("/health")
def health():
    return {"ok": True, "time": datetime.now().isoformat()}

# ----------------- Auth (Supabase email/password) -----------------
# POST /signup?email=you@example.com&password=secret123
@app.post("/signup")
def signup(email: str, password: str):
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        user = res.user
        if not user:
            raise HTTPException(status_code=400, detail="Signup failed (no user returned)")
        return {"user_id": user.id, "email": user.email}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Signup failed: {e}")

# POST /login?email=you@example.com&password=secret
@app.post("/login")
def login(email: str, password: str):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        user = res.user
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return {"user_id": user.id, "email": user.email}
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Login failed: {e}")

# ----------------- Messaging -----------------
# POST /message?user_id=...&content=...&emoji=&language=en
@app.post("/message")
def save_message(user_id: str, content: str, emoji: str = "", language: str = "en"):
    try:
        key = (content or "").strip().lower()
        if not emoji and key in EMOJI_MAP:
            emoji = EMOJI_MAP[key]

        data = {
            "user_id": user_id,
            "content": content,
            "emoji": emoji,
            "language": language,
            "timestamp": datetime.now().isoformat(),
        }
        supabase.table("messages").insert(data).execute()
        return {"status": "saved", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB insert failed: {e}")

# GET /history/{user_id}
@app.get("/history/{user_id}")
def get_history(user_id: str):
    try:
        res = (
            supabase.table("messages")
            .select("*")
            .eq("user_id", user_id)
            .order("timestamp", desc=False)
            .execute()
        )
        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB fetch failed: {e}")

# DELETE /history/{user_id}
@app.delete("/history/{user_id}")
def clear_history(user_id: str):
    try:
        supabase.table("messages").delete().eq("user_id", user_id).execute()
        return {"status": "cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB delete failed: {e}")

# ----------------- Translation (EN -> target) -----------------
# GET /translate?text=Hello&lang=ta
@app.get("/translate")
def translate(text: str, lang: str):
    try:
        url = f"https://api.mymemory.translated.net/get?q={requests.utils.quote(text)}&langpair=en|{lang}"
        res = requests.get(url, timeout=10).json()
        out = res.get("responseData", {}).get("translatedText", "")
        return {"translated": out}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Translate failed: {e}")

# ----------------- Personal Dictionary (Custom Gestures) -----------------
# Table expected:
# custom_gestures(id uuid pk, user_id uuid, name text, sample_idx int, seq_json jsonb, created_at timestamptz)

# POST /custom_gesture/save?user_id=...&name=Amma&sample_idx=1
# body: {"frames": [[flattened landmark vec per frame], ...]}
@app.post("/custom_gesture/save")
def custom_gesture_save(
    user_id: str,
    name: str,
    sample_idx: int,
    seq_json: Dict[str, Any] = Body(...),
):
    try:
        if not isinstance(seq_json, dict) or "frames" not in seq_json:
            raise HTTPException(status_code=400, detail="seq_json must contain 'frames'")
        supabase.table("custom_gestures").insert({
            "user_id": user_id,
            "name": name,
            "sample_idx": sample_idx,
            "seq_json": seq_json,
        }).execute()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"save_custom_gesture failed: {e}")

# GET /custom_gesture/list?user_id=...
# returns: [{"name":"Amma","samples":8}, ...]
@app.get("/custom_gesture/list")
def custom_gesture_list(user_id: str):
    try:
        res = supabase.table("custom_gestures").select("name,sample_idx").eq("user_id", user_id).execute()
        counts: Dict[str, int] = {}
        for row in (res.data or []):
            counts[row["name"]] = counts.get(row["name"], 0) + 1
        return [{"name": k, "samples": v} for k, v in counts.items()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"list_custom_gestures failed: {e}")

# GET /custom_gesture/samples?user_id=...&name=optional
# returns rows with {name, seq_json}
@app.get("/custom_gesture/samples")
def custom_gesture_samples(user_id: str, name: str = ""):
    try:
        q = supabase.table("custom_gestures").select("name,seq_json").eq("user_id", user_id)
        if name:
            q = q.eq("name", name)
        res = q.execute()
        return res.data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"custom_gesture_samples failed: {e}")
class Room:
    def __init__(self):
        self.clients: List[WebSocket] = []
        self.peer_ids: Dict[WebSocket, str] = {}

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.clients.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.clients:
            self.clients.remove(ws)
        self.peer_ids.pop(ws, None)

    async def set_peer(self, ws: WebSocket, peer_id: str):
        self.peer_ids[ws] = peer_id
        await self.broadcast_state()

    async def broadcast_state(self):
        peers = [pid for pid in self.peer_ids.values() if pid]
        msg = {"type": "peers", "peers": peers}
        for cli in list(self.clients):
            try:
                await cli.send_json(msg)
            except Exception:
                pass

ROOMS: Dict[str, Room] = {}

@app.websocket("/ws/room/{room_code}")
async def ws_room(websocket: WebSocket, room_code: str):
    room = ROOMS.setdefault(room_code, Room())
    await room.connect(websocket)
    try:
        # First message expected: {"type":"hello","peerId":"<peerjs-id>","userId":"<uid>"}
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "hello":
                await room.set_peer(websocket, data.get("peerId") or "")
            # you can add ping/pong or caption broadcast here if you ever want server-side relay
    except WebSocketDisconnect:
        room.disconnect(websocket)
        await room.broadcast_state()
    except Exception:
        room.disconnect(websocket)
        await room.broadcast_state()    
