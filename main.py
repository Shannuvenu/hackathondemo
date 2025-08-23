# main.py
from fastapi import FastAPI, HTTPException, Body, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from dotenv import load_dotenv
from typing import Dict, Any, List
from supabase import create_client
import requests
import os

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

app = FastAPI(title="SignCall Backend", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

EMOJI_MAP = {"yes": "👍", "no": "👎", "hello": "✌"}

@app.get("/health")
def health():
    return {"ok": True, "time": datetime.now().isoformat()}

# ---------- Auth ----------
@app.post("/signup")
def signup(email: str, password: str):
    if not supabase:
        raise HTTPException(400, "Supabase not configured on server.")
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        user = res.user
        if not user:
            raise HTTPException(status_code=400, detail="Signup failed (no user returned)")
        return {"user_id": user.id, "email": user.email}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Signup failed: {e}")

@app.post("/login")
def login(email: str, password: str):
    if not supabase:
        raise HTTPException(400, "Supabase not configured on server.")
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        user = res.user
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return {"user_id": user.id, "email": user.email}
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Login failed: {e}")

# ---------- Messages ----------
@app.post("/message")
def save_message(user_id: str, content: str, emoji: str = "", language: str = "en"):
    if not supabase:
        # fall back: pretend saved, return echo (so front-end still works without DB)
        key = (content or "").strip().lower()
        emoji = emoji or EMOJI_MAP.get(key, "")
        return {"status": "ok_no_db", "data": {
            "user_id": user_id, "content": content, "emoji": emoji,
            "language": language, "timestamp": datetime.now().isoformat()
        }}
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

@app.get("/history/{user_id}")
def get_history(user_id: str):
    if not supabase:
        return []  # no DB -> just return empty history
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

@app.delete("/history/{user_id}")
def clear_history(user_id: str):
    if not supabase:
        return {"status": "ok_no_db"}
    try:
        supabase.table("messages").delete().eq("user_id", user_id).execute()
        return {"status": "cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB delete failed: {e}")

# ---------- Translate ----------
@app.get("/translate")
def translate(text: str, lang: str):
    try:
        url = f"https://api.mymemory.translated.net/get?q={requests.utils.quote(text)}&langpair=en|{lang}"
        res = requests.get(url, timeout=10).json()
        out = res.get("responseData", {}).get("translatedText", "")
        return {"translated": out}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Translate failed: {e}")

# ---------- Personal dictionary (optional; safe if no DB) ----------
@app.post("/custom_gesture/save")
def custom_gesture_save(user_id: str, name: str, sample_idx: int, seq_json: Dict[str, Any] = Body(...)):
    if not supabase:
        return {"ok": True, "note": "no DB configured"}
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

@app.get("/custom_gesture/list")
def custom_gesture_list(user_id: str):
    if not supabase:
        return []
    try:
        res = supabase.table("custom_gestures").select("name,sample_idx").eq("user_id", user_id).execute()
        counts: Dict[str, int] = {}
        for row in (res.data or []):
            counts[row["name"]] = counts.get(row["name"], 0) + 1
        return [{"name": k, "samples": v} for k, v in counts.items()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"list_custom_gestures failed: {e}")

@app.get("/custom_gesture/samples")
def custom_gesture_samples(user_id: str, name: str = ""):
    if not supabase:
        return []
    try:
        q = supabase.table("custom_gestures").select("name,seq_json").eq("user_id", user_id)
        if name:
            q = q.eq("name", name)
        res = q.execute()
        return res.data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"custom_gesture_samples failed: {e}")

# ---------- WebSocket rooms ----------
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
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "hello":
                await room.set_peer(websocket, data.get("peerId") or "")
    except WebSocketDisconnect:
        room.disconnect(websocket)
        await room.broadcast_state()
    except Exception:
        room.disconnect(websocket)
        await room.broadcast_state()

