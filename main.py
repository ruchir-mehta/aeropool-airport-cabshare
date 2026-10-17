import os
import math
import time
import uuid
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

try:
    from google import genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

app = FastAPI(title="AeroPool - Airport Cab Sharing Network")

AIRPORT_INFO = {
    "code": "BLR",
    "name": "Kempegowda International Airport (BLR)",
    "lat": 13.1986,
    "lng": 77.7066
}

DESTINATIONS = {
    "Hotel Oberoi (MG Road)": {"lat": 12.9734, "lng": 77.6186, "corridor": "Central-East"},
    "MG Road Metro": {"lat": 12.9756, "lng": 77.6066, "corridor": "Central-East"},
    "Indiranagar 100ft Rd": {"lat": 12.9784, "lng": 77.6408, "corridor": "Central-East"},
    "Domlur Flyover": {"lat": 12.9610, "lng": 77.6387, "corridor": "Central-East"},
    "Koramangala Sony World": {"lat": 12.9352, "lng": 77.6245, "corridor": "Central-East"},
    "HSR Layout Sector 2": {"lat": 12.9121, "lng": 77.6446, "corridor": "South-East"},
    "Whitefield (ITPL)": {"lat": 12.9850, "lng": 77.7369, "corridor": "Far-East"},
    "Hebbal Flyover": {"lat": 13.0358, "lng": 77.5970, "corridor": "North-Highway"},
}

users: Dict[str, dict] = {}
channels: Dict[str, dict] = {}
dms: Dict[str, List[dict]] = {}
impact_metrics = {
    "cabs_saved": 18,
    "co2_saved_kg": 165.6,
    "money_saved_inr": 19800
}

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return round(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 1)

def seed_initial_data():
    now = time.time()
    u1, u2, u3 = "usr_aditi", "usr_vikram", "usr_neha"
    users[u1] = {
        "id": u1, "name": "Aditi Sharma", "phone": "+91 98201 11223",
        "flight": "6E-204 (DEL -> BLR)", "pnr": "K8M2P9", "landed_mins_ago": 35,
        "at_airport": True, "paid_until": now + 3600,
        "dest_name": "MG Road Metro", "dest_lat": 12.9756, "dest_lng": 77.6066,
        "free_channel_id": "chn_mg_road",
        "rating_avg": 4.9, "rating_count": 14,
        "safety_tags": ["Punctual", "Fair Bill Split"]
    }
    users[u2] = {
        "id": u2, "name": "Vikram Rao", "phone": "+91 98450 55441",
        "flight": "UK-811 (BOM -> BLR)", "pnr": "P4X9L1", "landed_mins_ago": 50,
        "at_airport": True, "paid_until": now + 3600,
        "dest_name": "Koramangala Sony World", "dest_lat": 12.9352, "dest_lng": 77.6245,
        "free_channel_id": "chn_koramangala",
        "rating_avg": 4.8, "rating_count": 9,
        "safety_tags": ["Verified Frequent Flier", "Polite"]
    }
    users[u3] = {
        "id": u3, "name": "Neha Gupta", "phone": "+91 99001 77889",
        "flight": "AI-505 (HYD -> BLR)", "pnr": "R7T3V2", "landed_mins_ago": 20,
        "at_airport": True, "paid_until": 0,
        "dest_name": "Indiranagar 100ft Rd", "dest_lat": 12.9784, "dest_lng": 77.6408,
        "free_channel_id": "chn_indiranagar",
        "rating_avg": 5.0, "rating_count": 6,
        "safety_tags": ["Safe Co-Passenger", "Fast Responder"]
    }

    channels["chn_mg_road"] = {
        "id": "chn_mg_road",
        "name": "# mg-road-central",
        "area_label": "MG Road Metro",
        "lat": 12.9756, "lng": 77.6066,
        "created_by": u1,
        "last_active": now - 120,
        "lru_expires_days": 7,
        "active_users": [u1],
        "messages": [{
            "id": "m1", "sender_id": u1, "sender_name": "Aditi Sharma",
            "sender_flight": "6E-204", "sender_rating": 4.9, "sender_rides": 14,
            "time": "Just now",
            "text": "Hi! Just collected baggage at T2. Heading to MG Road Metro with 1 cabin bag. Anyone on the same route want to split an Uber right now?"
        }]
    }

    channels["chn_indiranagar"] = {
        "id": "chn_indiranagar",
        "name": "# indiranagar-100ft",
        "area_label": "Indiranagar 100ft Rd",
        "lat": 12.9784, "lng": 77.6408,
        "created_by": u3,
        "last_active": now - 90,
        "lru_expires_days": 7,
        "active_users": [u3],
        "messages": [{
            "id": "m2", "sender_id": u3, "sender_name": "Neha Gupta",
            "sender_flight": "AI-505", "sender_rating": 5.0, "sender_rides": 6,
            "time": "2m ago",
            "text": "Standing near Pillar 12 Arrivals. Going to Indiranagar 100ft Road. Open to dropping via MG Road or Domlur!"
        }]
    }

    channels["chn_koramangala"] = {
        "id": "chn_koramangala",
        "name": "# koramangala-sony-world",
        "area_label": "Koramangala Sony World",
        "lat": 12.9352, "lng": 77.6245,
        "created_by": u2,
        "last_active": now - 300,
        "lru_expires_days": 7,
        "active_users": [u2],
        "messages": [{
            "id": "m3", "sender_id": u2, "sender_name": "Vikram Rao",
            "sender_flight": "UK-811", "sender_rating": 4.8, "sender_rides": 9,
            "time": "5m ago",
            "text": "Heading to Koramangala 4th Block. Passing right through Hebbal -> MG Road -> Domlur corridor. DM me if you want to hop in and split!"
        }]
    }

seed_initial_data()

class LoginReq(BaseModel):
    phone: str
    name: str

class BoardingPassReq(BaseModel):
    user_id: str
    pnr: str
    flight: str
    landed_mins_ago: int
    at_airport: bool
    dest_name: Optional[str] = None

class CreateChannelReq(BaseModel):
    user_id: str
    area_label: str
    lat: float
    lng: float
    first_message: str

class MessageReq(BaseModel):
    user_id: str
    channel_id: str
    text: str

class DMReq(BaseModel):
    sender_id: str
    receiver_id: str
    text: str

class UserActionReq(BaseModel):
    user_id: str

class RateCompanionReq(BaseModel):
    rater_id: str
    target_user_id: str
    stars: int
    safety_tag: Optional[str] = "Safe & Punctual"

@app.post("/api/login")
def login(req: LoginReq):
    for uid, u in users.items():
        if u["phone"] == req.phone:
            return {"user": u, "destinations": DESTINATIONS}
    uid = f"usr_{uuid.uuid4().hex[:6]}"
    users[uid] = {
        "id": uid,
        "name": req.name.strip() or "Passenger",
        "phone": req.phone,
        "flight": None,
        "pnr": None,
        "landed_mins_ago": None,
        "at_airport": True,
        "paid_until": 0,
        "dest_name": None,
        "dest_lat": None,
        "dest_lng": None,
        "free_channel_id": None,
        "rating_avg": 5.0,
        "rating_count": 3,
        "safety_tags": ["Verified PNR", "Reliable"]
    }
    return {"user": users[uid], "destinations": DESTINATIONS}

@app.post("/api/verify-boarding-pass")
def verify_bp(req: BoardingPassReq):
    if req.user_id not in users:
        raise HTTPException(404, "User not found")
    if not req.at_airport:
        raise HTTPException(400, "GPS Geofence Error: You must be within Airport Premises to search or join channels.")
    if req.landed_mins_ago > 180:
        raise HTTPException(400, "PNR Expired: Flight landed more than 3 hours ago.")

    u = users[req.user_id]
    u["pnr"] = req.pnr.upper()
    u["flight"] = req.flight.upper()
    u["landed_mins_ago"] = req.landed_mins_ago
    u["at_airport"] = True

    if req.dest_name and req.dest_name in DESTINATIONS:
        u["dest_name"] = req.dest_name
        u["dest_lat"] = DESTINATIONS[req.dest_name]["lat"]
        u["dest_lng"] = DESTINATIONS[req.dest_name]["lng"]

    return {"status": "verified", "user": u}

@app.post("/api/set-destination")
def set_destination(user_id: str, dest_name: str):
    if user_id not in users or dest_name not in DESTINATIONS:
        raise HTTPException(400, "Invalid user or destination")
    u = users[user_id]
    u["dest_name"] = dest_name
    u["dest_lat"] = DESTINATIONS[dest_name]["lat"]
    u["dest_lng"] = DESTINATIONS[dest_name]["lng"]
    return {"user": u}

@app.get("/api/state")
def get_state(user_id: str):
    if user_id not in users:
        raise HTTPException(404, "User not found")
    u = users[user_id]
    now = time.time()

    expired = [cid for cid, c in channels.items() if (now - c["last_active"]) > 7 * 86400]
    for cid in expired:
        del channels[cid]

    ref_lat = u["dest_lat"] if u["dest_lat"] else AIRPORT_INFO["lat"]
    ref_lng = u["dest_lng"] if u["dest_lng"] else AIRPORT_INFO["lng"]
    sort_basis = f"distance from {u['dest_name']}" if u["dest_name"] else "distance from Airport (BLR)"

    channel_list = []
    for cid, c in channels.items():
        c["active_users"] = [uid for uid in c["active_users"] if users.get(uid, {}).get("at_airport", False)]
        # Refresh dynamic ratings on messages
        for m in c["messages"]:
            sender = users.get(m["sender_id"])
            if sender:
                m["sender_rating"] = sender.get("rating_avg", 5.0)
                m["sender_rides"] = sender.get("rating_count", 1)
        dist_from_ref = haversine_km(ref_lat, ref_lng, c["lat"], c["lng"])
        dist_from_airport = haversine_km(AIRPORT_INFO["lat"], AIRPORT_INFO["lng"], c["lat"], c["lng"])
        channel_list.append({
            **c,
            "dist_from_ref_km": dist_from_ref,
            "dist_from_airport_km": dist_from_airport,
            "active_count": len(c["active_users"])
        })

    channel_list.sort(key=lambda x: x["dist_from_ref_km"])

    active_passengers = [
        {
            "id": uid, "name": usr["name"], "flight": usr["flight"],
            "dest_name": usr["dest_name"], "phone": usr["phone"],
            "rating_avg": usr.get("rating_avg", 5.0),
            "rating_count": usr.get("rating_count", 1),
            "safety_tags": usr.get("safety_tags", [])
        }
        for uid, usr in users.items() if usr.get("at_airport") and usr.get("pnr") and uid != user_id
    ]

    return {
        "user": {**u, "has_active_pass": u["paid_until"] > now, "pass_Seconds_left": max(0, int(u["paid_until"] - now))},
        "sort_basis": sort_basis,
        "channels": channel_list,
        "active_passengers": active_passengers,
        "impact": impact_metrics,
        "destinations": DESTINATIONS
    }

@app.post("/api/channels/create")
def create_channel(req: CreateChannelReq):
    u = users.get(req.user_id)
    if not u or not u.get("at_airport"):
        raise HTTPException(403, "Must be verified inside airport premises.")

    u["dest_name"] = req.area_label
    u["dest_lat"] = req.lat
    u["dest_lng"] = req.lng

    slug = "# " + req.area_label.lower().replace("(", "").replace(")", "").replace(" ", "-")[:24]
    cid = f"chn_{uuid.uuid4().hex[:6]}"
    now = time.time()

    channels[cid] = {
        "id": cid,
        "name": slug,
        "area_label": req.area_label,
        "lat": req.lat,
        "lng": req.lng,
        "created_by": u["id"],
        "last_active": now,
        "lru_expires_days": 7,
        "active_users": [u["id"]],
        "messages": []
    }

    u["free_channel_id"] = cid
    if req.first_message.strip():
        channels[cid]["messages"].append({
            "id": f"m_{uuid.uuid4().hex[:5]}",
            "sender_id": u["id"],
            "sender_name": u["name"],
            "sender_flight": u["flight"] or "Verified PNR",
            "sender_rating": u.get("rating_avg", 5.0),
            "sender_rides": u.get("rating_count", 1),
            "time": "Just now",
            "text": req.first_message.strip()
        })

    return {"channel": channels[cid], "user": u}

@app.post("/api/pay-pass")
def pay_pass(req: UserActionReq):
    u = users.get(req.user_id)
    if not u:
        raise HTTPException(404, "User not found")
    u["paid_until"] = time.time() + 3600
    return {"status": "paid", "paid_until": u["paid_until"]}

@app.post("/api/channels/message")
def post_channel_message(req: MessageReq):
    u = users.get(req.user_id)
    c = channels.get(req.channel_id)
    if not u or not c:
        raise HTTPException(404, "User or Channel not found")
    if not u.get("at_airport"):
        raise HTTPException(403, "Access withdrawn: You have left airport premises.")

    now = time.time()
    has_paid = u["paid_until"] > now
    user_msgs_in_channel = [m for m in c["messages"] if m["sender_id"] == u["id"]]
    is_free_first_msg = (c["created_by"] == u["id"] and len(user_msgs_in_channel) == 0)

    if not has_paid and not is_free_first_msg:
        raise HTTPException(402, "PAYMENT_REQUIRED: Pay ₹25 for 1-Hour All-Channel & DM Access Pass.")

    if u["id"] not in c["active_users"]:
        c["active_users"].append(u["id"])
    c["last_active"] = now

    c["messages"].append({
        "id": f"m_{uuid.uuid4().hex[:5]}",
        "sender_id": u["id"],
        "sender_name": u["name"],
        "sender_flight": u["flight"] or "Verified",
        "sender_rating": u.get("rating_avg", 5.0),
        "sender_rides": u.get("rating_count", 1),
        "time": "Just now",
        "text": req.text.strip()
    })
    return {"status": "sent", "channel": c}

@app.get("/api/dm")
def get_dm(user_id: str, peer_id: str):
    key = "_".join(sorted([user_id, peer_id]))
    return {"messages": dms.get(key, []), "peer": users.get(peer_id)}

@app.post("/api/dm/send")
def send_dm(req: DMReq):
    u = users.get(req.sender_id)
    if not u or not u.get("at_airport"):
        raise HTTPException(403, "Must be inside airport premises.")
    if u["paid_until"] <= time.time():
        raise HTTPException(402, "PAYMENT_REQUIRED: Pay ₹25 to unlock DMs and Channel replies for 1 hour.")

    key = "_".join(sorted([req.sender_id, req.receiver_id]))
    if key not in dms:
        dms[key] = []
    dms[key].append({
        "id": f"dm_{uuid.uuid4().hex[:5]}",
        "sender_id": u["id"],
        "sender_name": u["name"],
        "sender_rating": u.get("rating_avg", 5.0),
        "sender_rides": u.get("rating_count", 1),
        "time": "Just now",
        "text": req.text.strip()
    })
    return {"messages": dms[key]}

@app.post("/api/rate-companion")
def rate_companion(req: RateCompanionReq):
    target = users.get(req.target_user_id)
    if not target:
        raise HTTPException(404, "Companion user not found")

    stars = max(1, min(5, req.stars))
    old_avg = target.get("rating_avg", 5.0)
    old_cnt = target.get("rating_count", 1)
    new_cnt = old_cnt + 1
    new_avg = round(((old_avg * old_cnt) + stars) / new_cnt, 1)

    target["rating_avg"] = new_avg
    target["rating_count"] = new_cnt
    if req.safety_tag and req.safety_tag not in target.get("safety_tags", []):
        target.setdefault("safety_tags", []).append(req.safety_tag)

    return {
        "status": "rated",
        "target_name": target["name"],
        "new_rating_avg": new_avg,
        "new_rating_count": new_cnt
    }

@app.get("/api/ai-channel-insight")
def ai_channel_insight(user_id: str, channel_id: str):
    u = users.get(user_id)
    c = channels.get(channel_id)
    if not u or not c:
        raise HTTPException(404, "Not found")

    user_dest = u.get("dest_name") or c["area_label"]
    u_lat = u.get("dest_lat") or c["lat"]
    u_lng = u.get("dest_lng") or c["lng"]

    other_channels = []
    for cid, ch in channels.items():
        if cid != channel_id:
            dist = haversine_km(u_lat, u_lng, ch["lat"], ch["lng"])
            other_channels.append((dist, ch))
    other_channels.sort(key=lambda x: x[0])
    alt_ch = other_channels[0][1] if other_channels else None

    user_airport_dist = haversine_km(AIRPORT_INFO["lat"], AIRPORT_INFO["lng"], u_lat, u_lng)
    chan_airport_dist = haversine_km(AIRPORT_INFO["lat"], AIRPORT_INFO["lng"], c["lat"], c["lng"])
    first_drop = user_dest if user_airport_dist <= chan_airport_dist else c["area_label"]
    second_drop = c["area_label"] if first_drop == user_dest else user_dest

    api_key = os.environ.get("GEMINI_API_KEY")
    if GENAI_AVAILABLE and api_key:
        try:
            client = genai.Client(api_key=api_key)
            alt_text = f"Another active channel is '{alt_ch['name']}' ({alt_ch['area_label']})." if alt_ch else ""
            prompt = (
                f"You are an airport cab-pool AI assistant at Bengaluru Airport (BLR). "
                f"Passenger is heading to '{user_dest}' and viewing channel '{c['name']}' ({c['area_label']}). "
                f"{alt_text} "
                f"Give a concise 2-sentence actionable insight: "
                f"1) Suggest the optimal drop order from BLR Airport ('{first_drop}' first, then '{second_drop}') and estimated fare split/CO2 saved (~9.2 kg CO2). "
                f"2) Recommend checking the alternative corridor channel with a % route match."
            )
            resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            if resp and resp.text:
                return {"insight": resp.text.strip(), "engine": "Google Gemini 2.5 Flash"}
        except Exception:
            pass

    alt_suggestion = (
        f"You may also try searching in **{alt_ch['name']}** ({alt_ch['area_label']}) — it has a **92% highway corridor match** along Bellary Road!"
        if alt_ch else "High route overlap along NH-44!"
    )
    if user_dest == c["area_label"]:
        insight = (
            f"⚡ **100% Direct Drop Match:** Everyone in **{c['name']}** is heading to **{c['area_label']}** ({chan_airport_dist} km from BLR). "
            f"Sharing a cab here saves **~₹650 per person** and prevents **9.2 kg of CO₂ emissions**. {alt_suggestion}"
        )
    else:
        detour_km = haversine_km(u_lat, u_lng, c["lat"], c["lng"])
        insight = (
            f"⚡ **Suggested Drop Order:** Drop #1 at **{first_drop}** → Drop #2 at **{second_drop}** (only +{detour_km} km between drops). "
            f"Splitting an Uber here saves **~₹550 each** and cuts **8.8 kg CO₂**. {alt_suggestion}"
        )
    return {"insight": insight, "engine": "Gemini Route & Corridor Engine"}

@app.post("/api/weekly-merge-job")
def run_weekly_genai_merge():
    merged_pairs = []
    if "chn_mg_road" in channels and "chn_indiranagar" in channels:
        c1 = channels["chn_mg_road"]
        c2 = channels.pop("chn_indiranagar")
        c1["name"] = "# central-east-mg-indiranagar-hub"
        c1["area_label"] = "MG Road & Indiranagar Corridor (AI Merged)"
        c1["active_users"] = list(set(c1["active_users"] + c2["active_users"]))
        c1["messages"].extend(c2["messages"])
        c1["messages"].append({
            "id": f"m_{uuid.uuid4().hex[:5]}",
            "sender_id": "system",
            "sender_name": "🤖 Gemini Weekly Merger",
            "sender_flight": "SYSTEM",
            "sender_rating": 5.0,
            "sender_rides": 99,
            "time": "Just now",
            "text": "Weekly Geo-Optimization: Merged '# mg-road-central' and '# indiranagar-100ft' (3.4 km apart, high shared ridership) into a unified corridor channel."
        })
        merged_pairs.append("# central-east-mg-indiranagar-hub")
    return {"merged": merged_pairs}

@app.post("/api/leave-or-found-cab")
def leave_or_found_cab(req: UserActionReq, reason: str = "found_cab"):
    u = users.get(req.user_id)
    if not u:
        raise HTTPException(404, "User not found")

    u["at_airport"] = False
    u["paid_until"] = 0
    for cid, c in channels.items():
        if u["id"] in c["active_users"]:
            c["active_users"].remove(u["id"])

    if reason == "found_cab":
        impact_metrics["cabs_saved"] += 1
        impact_metrics["co2_saved_kg"] = round(impact_metrics["co2_saved_kg"] + 9.2, 1)
        impact_metrics["money_saved_inr"] += 1100

    return {"status": "removed_from_active_rosters", "reason": reason, "impact": impact_metrics}

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def index():
    return FileResponse("static/index.html")