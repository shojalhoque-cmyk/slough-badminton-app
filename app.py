import streamlit as st
import pandas as pd
import random
import urllib.parse
from datetime import datetime
from zoneinfo import ZoneInfo
from supabase import create_client, Client
import math
import time

st.set_page_config(page_title="Slough Badminton Club (Monday)", page_icon="🏸", layout="wide")

# --- MOBILE-FIRST CSS OVERRIDES ---
st.markdown("""
<style>
    .block-container { padding-top: 0.5rem !important; padding-bottom: 2rem !important; padding-left: 0.75rem !important; padding-right: 0.75rem !important; }
    .stButton button { border-radius: 10px; font-weight: bold; width: 100%; min-height: 45px; }
    div[data-testid="stVerticalBlock"] > div { margin-bottom: -0.1rem; }
    div[data-testid="stDataFrame"] { width: 100% !important; overflow-x: auto; }
    button[data-baseweb="tab"] { font-size: 14px !important; font-weight: bold !important; padding: 8px 12px !important; }
    .ticker-box { background-color: #1E232F; padding: 10px 15px; border-radius: 8px; border-left: 4px solid #FF4B4B; margin-bottom: 15px; font-size: 14px; }
</style>
""", unsafe_allow_html=True)

# --- SUPABASE DATABASE CONNECTION ---
@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase: Client = init_supabase()
except Exception as e:
    st.error("Could not connect to Supabase database. Please verify Streamlit secrets.")

ADMIN_ACCOUNTS = {
    "admin": "4dm1n776&",
    "Musa": "4dmiN786&",
    "Simon": "4dm1nh3ll0",
    "Aaron": "A4dm1n1"
}

DEFAULT_MASTER_ROSTER = [
    "Shoj", "Abdul Waheed", "Aaron", "Faisal", "Naveed", 
    "AbdulKhader", "Ryan", "Abdullah sr", "Yousuf", "Aamer", 
    "Mohsin", "Simon", "Joe S", "Hassan", "Habeeb"
]

def load_master_player_list():
    try:
        resp = supabase.table("master_player_list").select("*").eq("id", 1).execute()
        if resp.data and "players" in resp.data[0]:
            return resp.data[0]["players"]
    except Exception:
        pass
    return DEFAULT_MASTER_ROSTER

def save_master_player_list(players_list):
    try:
        supabase.table("master_player_list").upsert({
            "id": 1,
            "players": players_list
        }).execute()
        return True
    except Exception as e:
        st.error(f"Error saving master player list: {e}")
        return False

def load_global_session_state():
    try:
        resp = supabase.table("session_state").select("*").eq("id", 1).execute()
        if resp.data:
            row = resp.data[0]
            st.session_state.current_session_num = row.get("current_session_num", 1)
            st.session_state.active_players = row.get("active_players", [])
            st.session_state.session_scores = row.get("session_scores", {})
            st.session_state.league_standings = row.get("league_standings", {})
            st.session_state.play_counts = row.get("play_counts", {})
            st.session_state.player_emojis = row.get("player_emojis", {})
            st.session_state.live_ticker = row.get("live_ticker", [])
    except Exception:
        pass

def save_global_session_state():
    try:
        supabase.table("session_state").upsert({
            "id": 1,
            "current_session_num": st.session_state.get("current_session_num", 1),
            "active_players": st.session_state.get("active_players", []),
            "session_scores": st.session_state.get("session_scores", {}),
            "league_standings": st.session_state.get("league_standings", {}),
            "play_counts": st.session_state.get("play_counts", {}),
            "player_emojis": st.session_state.get("player_emojis", {}),
            "live_ticker": st.session_state.get("live_ticker", [])
        }).execute()
    except Exception:
        pass

def fetch_permanent_match_history():
    try:
        resp = supabase.table("match_history_log").select("*").order("id", desc=False).execute()
        return resp.data if resp.data else []
    except Exception:
        return []

def log_match_to_database(session_num, team1, team2, s1, s2):
    try:
        supabase.table("match_history_log").insert({
            "session_num": session_num,
            "team_a": team1,
            "team_b": team2,
            "score_a": s1,
            "score_b": s2
        }).execute()
    except Exception as e:
        st.error(f"Error logging match: {e}")

def fetch_live_courts():
    try:
        resp = supabase.table("live_courts").select("*").execute()
        courts = {}
        if resp.data:
            for row in resp.data:
                c_id = row["court_id"]
                if row.get("team_a") and row.get("team_b"):
                    courts[c_id] = {
                        "team1": row["team_a"],
                        "team2": row["team_b"]
                    }
                else:
                    courts[c_id] = None
        return courts
    except Exception:
        return {}

def update_live_court(court_num, team1=None, team2=None):
    try:
        supabase.table("live_courts").upsert({
            "court_id": court_num,
            "team_a": team1,
            "team_b": team2
        }).execute()
    except Exception:
        pass

def update_user_presence(username):
    try:
        now_uk = datetime.now(ZoneInfo("Europe/London")).isoformat()
        supabase.table("active_presence").upsert({
            "username": username,
            "last_seen": now_uk
        }).execute()
    except Exception:
        pass

def get_active_viewers():
    try:
        # Fetch users seen within the last 3 minutes
        now_utc = datetime.now(ZoneInfo("Europe/London"))
        resp = supabase.table("active_presence").select("username, last_seen").execute()
        active = []
        if resp.data:
            for row in resp.data:
                last_seen_dt = datetime.fromisoformat(row["last_seen"])
                diff_seconds = (now_utc - last_seen_dt).total_seconds()
                if diff_seconds <= 180:  # Active in last 3 minutes
                    active.append(row["username"])
        return active
    except Exception:
        return []

def get_user_role(username, password):
    if username in ADMIN_ACCOUNTS and ADMIN_ACCOUNTS[username] == password:
        return "admin"
    try:
        response = supabase.table("users").select("*").eq("username", username).eq("password", password).execute()
        if response.data: return response.data[0]["role"]
    except Exception:
        pass
    return None

def register_user(username, password):
    if username in ADMIN_ACCOUNTS:
        return False, "Username reserved for Admin."
    try:
        response = supabase.table("users").select("username").eq("username", username).execute()
        if response.data:
            return False, "Username already exists."
        supabase.table("users").insert({"username": username, "password": password, "role": "player"}).execute()
        return True, "Account created successfully!"
    except Exception as e:
        return False, f"Error creating account: {e}"

def log_login_event(username):
    try:
        now_uk = datetime.now(ZoneInfo("Europe/London")).strftime("%Y-%m-%d %H:%M:%S")
        supabase.table("login_logs").insert({"username": username, "login_time": now_uk}).execute()
    except Exception:
        pass

def is_session_active():
    now_uk = datetime.now(ZoneInfo("Europe/London"))
    return now_uk.weekday() == 0 and (20 <= now_uk.hour < 22)

query_params = st.query_params
saved_user = query_params.get("user")
saved_role = query_params.get("role")

if "logged_in" not in st.session_state or not st.session_state.logged_in:
    if saved_user and saved_role:
        st.session_state.logged_in = True
        st.session_state.username = saved_user
        st.session_state.role = saved_role
    else:
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.role = None

if "last_court_time" not in st.session_state:
    st.session_state.last_court_time = {}

if "roster_builder" not in st.session_state:
    st.session_state.roster_builder = load_master_player_list()

if "player_emojis" not in st.session_state:
    st.session_state.player_emojis = {}

if "live_ticker" not in st.session_state:
    st.session_state.live_ticker = ["👋 Welcome to Slough Badminton Club Mondays! Ready for action?"]

load_global_session_state()

if st.session_state.logged_in and st.session_state.username:
    update_user_presence(st.session_state.username)

RAW_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 260 260" width="260" height="260">
    <circle cx="130" cy="130" r="120" fill="#1E4867" stroke="#F9F8F3" stroke-width="6"/>
    <path id="archPath" d="M 35,130 A 95,95 0 1,1 225,130" fill="none" />
    <text fill="#F9F8F3" font-size="15" font-weight="900" font-family="Arial, sans-serif" letter-spacing="2">
        <textPath href="#archPath" startOffset="50%" text-anchor="middle">BADMINTON MONDAYS</textPath>
    </text>
    <text x="130" y="145" font-size="44" text-anchor="middle">🏸</text>
    <text x="130" y="172" font-size="13" fill="#F9F8F3" text-anchor="middle" letter-spacing="2">⭐⭐⭐⭐⭐</text>
    <text x="130" y="195" font-size="11" font-weight="bold" fill="#F9F8F3" text-anchor="middle" font-family="Arial, sans-serif">8PM - 10PM</text>
    <text x="130" y="212" font-size="11" font-weight="bold" fill="#F9F8F3" text-anchor="middle" font-family="Arial, sans-serif">DITTON PARK, SLOUGH</text>
</svg>"""
SVG_URL = "data:image/svg+xml;utf8," + urllib.parse.quote(RAW_SVG)

if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image(SVG_URL, width=160)
        st.title("Slough Badminton Club")
        login_tab, signup_tab = st.tabs(["🔒 Log In", "📝 Sign Up"])
        with login_tab:
            with st.form("login_form"):
                st.subheader("Log In")
                username_input = st.text_input("Username").strip()
                password_input = st.text_input("Password", type="password").strip()
                submit_button = st.form_submit_button("Log In", use_container_width=True)
                if submit_button:
                    role = get_user_role(username_input, password_input)
                    if role:
                        st.session_state.logged_in = True
                        st.session_state.username = username_input
                        st.session_state.role = role
                        st.query_params["user"] = username_input
                        st.query_params["role"] = role
                        log_login_event(username_input)
                        update_user_presence(username_input)
                        st.success(f"Welcome back, {username_input}!")
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")
        with signup_tab:
            with st.form("signup_form"):
                st.subheader("Create Account")
                new_user = st.text_input("Choose Username").strip()
                new_pass = st.text_input("Choose Password", type="password").strip()
                confirm_pass = st.text_input("Confirm Password", type="password").strip()
                signup_btn = st.form_submit_button("Create Account", use_container_width=True)
                if signup_btn:
                    if new_pass != confirm_pass: st.error("Passwords do not match.")
                    elif not new_user or not new_pass: st.error("Please fill in all fields.")
                    else:
                        success, msg = register_user(new_user, new_pass)
                        if success: st.success(msg)
                        else: st.error(msg)
    st.stop()

session_live = is_session_active()
can_edit = session_live or (st.session_state.role == "admin")
is_master_admin = (st.session_state.username == "admin")
can_manage_season = (st.session_state.username in ["admin", "Musa", "Aaron"])

st.sidebar.write(f"Logged in as: **{st.session_state.username}** ({st.session_state.role.capitalize()})")

# --- WHATSAPP GROUP LINK INTEGRATION ---
whatsapp_link = "https://chat.whatsapp.com/YOUR_WHATSAPP_GROUP_LINK_HERE"  # Replace with your actual invite link
st.sidebar.markdown(f'<a href="{whatsapp_link}" target="_blank"><button style="width:100%; background-color:#25D366; color:white; border:none; padding:10px; border-radius:8px; font-weight:bold; cursor:pointer;">💬 Open WhatsApp Group</button></a>', unsafe_allow_html=True)
st.sidebar.write("---")

# --- LIVE ACTIVE USERS SIDEBAR WIDGET ---
active_viewers = get_active_viewers()
st.sidebar.markdown(f"🟢 **Online Right Now ({len(active_viewers)}):**")
if active_viewers:
    st.sidebar.caption(", ".join([f"**{u}**" for u in active_viewers]))
else:
    st.sidebar.caption("No other active users detected.")
st.sidebar.write("---")

if st.session_state.role == "admin": st.sidebar.success("👑 **Admin User: Full Access Active 24/7**")
elif session_live: st.sidebar.success("🟢 **Session Active (8PM-10PM): Edit Mode Unlocked for All**")
else: st.sidebar.info("🔒 **Outside Session Hours: Read-Only Mode**")
if st.sidebar.button("Log Out", use_container_width=True):
    st.query_params.clear()
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.role = None
    st.rerun()

col_logo, col_title = st.columns([1, 4])
with col_logo: st.image(SVG_URL, width=80)
with col_title:
    st.title("Slough Badminton Club")
    st.caption(f"📅 Season Progress: Session {st.session_state.current_session_num} / 12")

tab_names = ["📊 Standings", "🔥 Hub", "🌙 Recap", "🏆 League"]
if can_edit: tab_names.insert(0, "🎾 Courts")
if can_manage_season: tab_names.append("⚙️ Season")
if is_master_admin: tab_names.append("👥 Users")

tabs = st.tabs(tab_names)
tab_courts = tabs[tab_names.index("🎾 Courts")] if "🎾 Courts" in tab_names else None
tab_standings = tabs[tab_names.index("📊 Standings")]
tab_hub = tabs[tab_names.index("🔥 Hub")]
tab_recap = tabs[tab_names.index("🌙 Recap")]
tab_league = tabs[tab_names.index("🏆 League")]
tab_season = tabs[tab_names.index("⚙️ Season")] if "⚙️ Season" in tab_names else None
tab_users = tabs[tab_names.index("👥 Users")] if "👥 Users" in tab_names else None

def get_player_display(name):
    emoji = st.session_state.player_emojis.get(name, "🏸")
    return f"{emoji} {name}"

def get_resting_players(courts_state):
    currently_playing = set()
    for c, match in courts_state.items():
        if match:
            currently_playing.update(match["team1"])
            currently_playing.update(match["team2"])
    
    resting = [p for p in st.session_state.active_players if p not in currently_playing]
    return sorted(resting, key=lambda p: (
        st.session_state.play_counts.get(p, 0), 
        st.session_state.last_court_time.get(p, 0)
    ))

def assign_next_match_to_court(court_num, courts_state):
    resting = get_resting_players(courts_state)
    if len(resting) >= 4:
        next_4 = resting[:4]
        team1 = [next_4[0], next_4[1]]
        team2 = [next_4[2], next_4[3]]
        
        current_time = time.time()
        for p in next_4: 
            st.session_state.play_counts[p] = st.session_state.play_counts.get(p, 0) + 1
            st.session_state.last_court_time[p] = current_time 
            
        update_live_court(court_num, team1, team2)
        save_global_session_state()
        return True
    else:
        update_live_court(court_num, None, None)
        return False

def process_court_finish_callback(court_num, match, s1_key, s2_key):
    s1 = st.session_state.get(s1_key, 0)
    s2 = st.session_state.get(s2_key, 0)
    
    if s1 < 21 and s2 < 21:
        st.session_state[f"msg_{court_num}"] = ("error", f"⚠️ Court {court_num}: At least one team must reach 21 points!")
        return
    if s1 == s2:
        st.session_state[f"msg_{court_num}"] = ("error", f"⚠️ Court {court_num}: Match cannot end in a draw!")
        return
        
    t1_p1, t1_p2 = match['team1'][0], match['team1'][1]
    t2_p1, t2_p2 = match['team2'][0], match['team2'][1]

    log_match_to_database(st.session_state.current_session_num, match["team1"], match["team2"], s1, s2)

    losing_team = match["team2"] if s1 > s2 else match["team1"]
    win_score = max(s1, s2)
    lose_score = min(s1, s2)

    for p in match["team1"]:
        if s1 > s2:
            st.session_state.session_scores[p] = st.session_state.session_scores.get(p, 0) + 2
            st.session_state.league_standings[p] = st.session_state.league_standings.get(p, 0) + 2

    for p in match["team2"]:
        if s2 > s1:
            st.session_state.session_scores[p] = st.session_state.session_scores.get(p, 0) + 2
            st.session_state.league_standings[p] = st.session_state.league_standings.get(p, 0) + 2

    margin = abs(s1 - s2)
    t1_names = f"{t1_p1} & {t1_p2}"
    t2_names = f"{t2_p1} & {t2_p2}"
    winner_str = t1_names if s1 > s2 else t2_names
    ticker_msg = f"🔥 Court {court_num}: {winner_str} won {win_score}-{lose_score} against {' & '.join(losing_team)}!"
    st.session_state.live_ticker.insert(0, ticker_msg)
    if len(st.session_state.live_ticker) > 5:
        st.session_state.live_ticker.pop()

    if margin <= 2:
        st.balloons()

    st.session_state.pop(s1_key, None)
    st.session_state.pop(s2_key, None)
    
    update_live_court(court_num, None, None)
    save_global_session_state()
    st.session_state[f"msg_{court_num}"] = ("success", f"Court {court_num} score saved successfully!")

# --- COURTS ---
if tab_courts:
    with tab_courts:
        if st.session_state.live_ticker:
            st.markdown(f'<div class="ticker-box">📢 <b>Courtside Broadcast:</b> {st.session_state.live_ticker[0]}</div>', unsafe_allow_html=True)

        if st.button("🔄 Refresh Live Courts", use_container_width=True):
            st.rerun()
            
        live_courts_state = fetch_live_courts()
        
        if not st.session_state.active_players:
            with st.container(border=True):
                st.subheader("👥 Players for today's session")
                st.caption("Add players, assign personal emojis, and tap 'Start session' when ready.")
                
                col_add_input, col_add_emoji, col_add_btn = st.columns([2, 1, 1])
                with col_add_input:
                    new_roster_name = st.text_input("Player Name", placeholder="Name...", label_visibility="collapsed", key="quick_add_roster")
                with col_add_emoji:
                    chosen_emoji = st.text_input("Emoji", value="🏸", max_chars=2, label_visibility="collapsed", key="quick_add_emoji")
                with col_add_btn:
                    if st.button("➕ Add", use_container_width=True):
                        if new_roster_name.strip():
                            clean_name = new_roster_name.strip()
                            if clean_name not in st.session_state.roster_builder:
                                st.session_state.roster_builder.append(clean_name)
                            st.session_state.player_emojis[clean_name] = chosen_emoji.strip() or "🏸"
                            st.rerun()
                        else:
                            st.warning("Enter a name.")
                
                st.write("---")
                st.markdown("**Current player list & emojis:**")
                
                for idx, player in enumerate(list(st.session_state.roster_builder)):
                    c_name, c_em, c_del = st.columns([3, 1, 1])
                    c_name.markdown(f"• **{player}**")
                    current_emo = st.session_state.player_emojis.get(player, "🏸")
                    new_emo = c_em.text_input("Emo", value=current_emo, max_chars=2, key=f"emo_{idx}", label_visibility="collapsed")
                    st.session_state.player_emojis[player] = new_emo
                    if c_del.button("❌", key=f"del_roster_{idx}"):
                        st.session_state.roster_builder.remove(player)
                        st.rerun()
                
                st.write("---")
                if st.button("💾 Save Player List & Emojis", use_container_width=True):
                    if save_master_player_list(st.session_state.roster_builder):
                        st.success("Master player list and emojis saved to Supabase!")
                
                st.write("---")
                num_courts = st.number_input("Number of Courts Available", min_value=1, max_value=6, value=3, key="num_courts_setup")
                
                if st.button("🚀 Start session with these players", type="primary", use_container_width=True):
                    if len(st.session_state.roster_builder) < 4:
                        st.error("You need at least 4 players to start a session.")
                    else:
                        names = list(st.session_state.roster_builder)
                        st.session_state.active_players = names
                        st.session_state.session_scores = {p: 0 for p in names}
                        st.session_state.play_counts = {p: 0 for p in names}
                        st.session_state.last_court_time = {p: 0 for p in names}
                        
                        for c in range(1, num_courts + 1):
                            update_live_court(c, None, None)
                        temp_courts = {}
                        for c in range(1, num_courts + 1):
                            assign_next_match_to_court(c, temp_courts)
                            temp_courts = fetch_live_courts()
                        save_global_session_state()
                        st.success(f"Session {st.session_state.current_session_num} started successfully!")
                        st.rerun()

        if st.session_state.active_players:
            with st.expander("👥 Manage Attendance (Add Late / Remove Early)", expanded=False):
                col_add1, col_add2 = st.columns([3, 1])
                with col_add1:
                    new_player_name = st.text_input("Late Arrival Name", placeholder="Enter name...", label_visibility="collapsed", key="midgame_add").strip()
                with col_add2:
                    if st.button("➕ Add", use_container_width=True):
                        if new_player_name:
                            if new_player_name not in st.session_state.active_players:
                                st.session_state.active_players.append(new_player_name)
                                st.session_state.session_scores.setdefault(new_player_name, 0)
                                st.session_state.play_counts.setdefault(new_player_name, 0)
                                st.session_state.last_court_time.setdefault(new_player_name, 0)
                                st.session_state.player_emojis.setdefault(new_player_name, "🏸")
                                st.session_state.league_standings.setdefault(new_player_name, 0)
                                save_global_session_state()
                                st.success(f"Added {new_player_name}!")
                                st.rerun()
                            else:
                                st.warning("Already active.")
                        else:
                            st.error("Enter a valid name.")

                st.write("---")
                st.caption("Active Players Tonight (Tap ❌ to remove):")
                
                for p in list(st.session_state.active_players):
                    col_pname, col_pdel = st.columns([4, 1])
                    col_pname.write(f"• **{get_player_display(p)}** ({st.session_state.play_counts.get(p, 0)} games)")
                    if col_pdel.button("❌", key=f"remove_{p}"):
                        st.session_state.active_players.remove(p)
                        save_global_session_state()
                        st.success(f"Removed {p}.")
                        st.rerun()

            resting_players = get_resting_players(live_courts_state)
            formatted_resting = [get_player_display(p) for p in resting_players]
            st.info(f"⏸️ **Queue ({len(resting_players)}):** {', '.join(formatted_resting) if formatted_resting else 'None'}")
            
            if st.button("💾 Save Everything to Database", type="secondary", use_container_width=True):
                save_global_session_state()
                st.success("Session state successfully saved to Supabase!")

            st.subheader("Live Courts")
            score_pill_options = [i for i in range(0, 31)]

            for court_num in range(1, 4):
                match = live_courts_state.get(court_num)
                msg = st.session_state.pop(f"msg_{court_num}", None)
                if msg:
                    if msg[0] == "error": st.error(msg[1])
                    elif msg[0] == "success": st.success(msg[1])

                with st.container(border=True):
                    st.markdown(f"#### 🏸 Court {court_num}")
                    if match:
                        t1_p1, t1_p2 = match['team1'][0], match['team1'][1]
                        t2_p1, t2_p2 = match['team2'][0], match['team2'][1]
                        
                        st.caption("🔵 **Team A**")
                        st.write(f"• **{get_player_display(t1_p1)}** & **{get_player_display(t1_p2)}**")
                        st.pills("Team A Score", options=score_pill_options, default=0, key=f"c{court_num}_s1_pills", label_visibility="collapsed")
                        
                        st.write("---")
                        st.caption("🔴 **Team B**")
                        st.write(f"• **{get_player_display(t2_p1)}** & **{get_player_display(t2_p2)}**")
                        st.pills("Team B Score", options=score_pill_options, default=0, key=f"c{court_num}_s2_pills", label_visibility="collapsed")
                        
                        st.write("")
                        st.button(f"💾 Save & Finish Court {court_num}", key=f"btn_{court_num}", type="primary", use_container_width=True, 
                                  on_click=process_court_finish_callback, 
                                  args=(court_num, match, f"c{court_num}_s1_pills", f"c{court_num}_s2_pills"))
                    else:
                        st.caption("No active match on this court.")
                        if st.button(f"⚡ Start Next Match on Court {court_num}", key=f"start_{court_num}", use_container_width=True):
                            assigned = assign_next_match_to_court(court_num, live_courts_state)
                            if not assigned: st.warning("Not enough players in queue.")
                            st.rerun()

with tab_standings:
    st.subheader(f"Today's Standings (Session {st.session_state.current_session_num}/12)")
    if st.session_state.session_scores:
        max_games = max(st.session_state.play_counts.values()) if st.session_state.play_counts else 0
        max_points = max(st.session_state.session_scores.values()) if st.session_state.session_scores else 0
        
        standings_data = []
        for k, v in st.session_state.session_scores.items():
            games = st.session_state.play_counts.get(k, 0)
            badges = []
            if games == max_games and games > 0: badges.append("🏃‍♂️ Marathon Runner")
            if v == max_points and v > 0: badges.append("⚡ Smashing Machine")
            
            standings_data.append({
                "Player": get_player_display(k),
                "Session Points": v,
                "Games Played": games,
                "Fun Badge": " · ".join(badges) if badges else "🔥 Contender"
            })
            
        df_today = pd.DataFrame(standings_data).sort_values(by="Session Points", ascending=False).reset_index(drop=True)
        df_today.index += 1
        st.dataframe(df_today, use_container_width=True)
    else:
        st.info("No games recorded for this session yet.")

with tab_hub:
    st.header("🔥 Club Hub & Rivalries")
    
    history = fetch_permanent_match_history()
    historical_players = set()
    for m in history:
        historical_players.update(m.get("team_a", []))
        historical_players.update(m.get("team_b", []))
    
    active_pool = sorted(list(set(st.session_state.get("active_players", [])).union(historical_players)))
    if not active_pool:
        active_pool = DEFAULT_MASTER_ROSTER
    
    if len(active_pool) >= 2:
        st.subheader("⚔️ Head-to-Head Lookup")
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            p1 = st.selectbox("Player 1", active_pool, index=0, key="hub_p1")
        with col_p2:
            p2 = st.selectbox("Player 2", active_pool, index=1 if len(active_pool) > 1 else 0, key="hub_p2")
            
        if p1 == p2:
            st.warning("Please select two different players.")
        else:
            p1_wins = 0
            p2_wins = 0
            meetings = 0
            
            for m in history:
                t1 = m.get("team_a", [])
                t2 = m.get("team_b", [])
                s1 = m.get("score_a", 0)
                s2 = m.get("score_b", 0)
                
                p1_in_t1 = p1 in t1
                p1_in_t2 = p1 in t2
                p2_in_t1 = p2 in t1
                p2_in_t2 = p2 in t2
                
                if (p1_in_t1 and p2_in_t2) or (p1_in_t2 and p2_in_t1):
                    meetings += 1
                    if p1_in_t1 and s1 > s2: p1_wins += 1
                    elif p1_in_t2 and s2 > s1: p1_wins += 1
                    elif p2_in_t1 and s1 > s2: p1_wins += 1
                    elif p2_in_t2 and s2 > s1: p1_wins += 1
                    
            c1, c2, c3 = st.columns(3)
            c1.metric(f"{get_player_display(p1)} Wins", p1_wins)
            c2.metric("Battles", meetings)
            c3.metric(f"{get_player_display(p2)} Wins", p2_wins)
            
            if meetings == 0:
                st.info("No recorded direct matches yet.")
        
        st.write("---")
        st.subheader("⚡ Player Form Barometer")
        selected_player = st.selectbox("Inspect Recent Form", active_pool, key="form_player_active")
        
        player_matches = []
        for m in history:
            t1 = m.get("team_a", [])
            t2 = m.get("team_b", [])
            if selected_player in t1 or selected_player in t2:
                in_t1 = selected_player in t1
                won = (in_t1 and m.get("score_a", 0) > m.get("score_b", 0)) or (not in_t1 and m.get("score_b", 0) > m.get("score_a", 0))
                player_matches.append("🟢 Win" if won else "🔴 Loss")
                
        if player_matches:
            recent_form = "  ".join(player_matches[-5:])
            st.write(f"**Last {min(5, len(player_matches))} matches for {get_player_display(selected_player)}:** {recent_form}")
        else:
            st.info("No match history recorded yet.")
    else:
        st.info("No players available for the Hub yet.")

with tab_recap:
    st.header("Night Recap")
    history = fetch_permanent_match_history()
    
    player_wins = {}
    total_points = {}
    close_matches = {}
    longest_match = {"s1": 0, "s2": 0}
    
    for m in history:
        s1, s2 = m.get("score_a", 0), m.get("score_b", 0)
        t1, t2 = m.get("team_a", []), m.get("team_b", [])
        if (s1 + s2) > (longest_match.get("s1", 0) + longest_match.get("s2", 0)):
            longest_match = {"t1": t1, "t2": t2, "s1": s1, "s2": s2}
        is_close = abs(s1 - s2) <= 2
        
        for p in t1:
            total_points[p] = total_points.get(p, 0) + s1 + s2
            if is_close: close_matches[p] = close_matches.get(p, 0) + 1
            if s1 > s2: player_wins[p] = player_wins.get(p, 0) + 1
        for p in t2:
            total_points[p] = total_points.get(p, 0) + s1 + s2
            if is_close: close_matches[p] = close_matches.get(p, 0) + 1
            if s2 > s1: player_wins[p] = player_wins.get(p, 0) + 1
            
    total_matches = len(history)
    current_date = datetime.now(ZoneInfo("Europe/London")).strftime("%d %B %Y")
    st.caption(f"{current_date} · SBC · {total_matches} matches")
    
    if total_matches > 0:
        if player_wins:
            champ = max(player_wins, key=player_wins.get)
            with st.container(border=True):
                st.caption("CHAMPION OF THE NIGHT")
                st.markdown(f"**{get_player_display(champ)}**")
                st.write(f"{player_wins[champ]} wins")
                
        if longest_match.get("s1"):
            with st.container(border=True):
                st.caption("LONGEST GAME PLAYED")
                st.markdown(f"**{longest_match['s1']}–{longest_match['s2']}**")
                t1_str = ' & '.join([get_player_display(x) for x in longest_match.get('t1', [])])
                t2_str = ' & '.join([get_player_display(x) for x in longest_match.get('t2', [])])
                st.write(f"{t1_str} vs {t2_str}")
                
        if close_matches:
            max_close = max(close_matches.values())
            heroes = [get_player_display(k) for k, v in close_matches.items() if v == max_close]
            with st.container(border=True):
                st.caption("CARDIAC KIDS (CLOSE MATCH HEROES)")
                st.markdown(f"**{' · '.join(heroes)}**")
                st.write(f"{max_close} nail-biting matches (2 pts or fewer)")
                
        if total_points:
            wh = max(total_points, key=total_points.get)
            with st.container(border=True):
                st.caption("THE WORKHORSE")
                st.markdown(f"**{get_player_display(wh)}**")
                st.write(f"{total_points[wh]} total points played")
    else:
        st.info("No games finished or recorded in history yet.")

with tab_league:
    st.subheader(f"🏆 12-Session Overall League ({st.session_state.current_session_num}/12)")
    if st.session_state.league_standings:
        league_data = []
        for k, v in st.session_state.league_standings.items():
            league_data.append({
                "Player": get_player_display(k),
                "RawName": k,
                "Total Points": v
            })
        df_league = pd.DataFrame(league_data).sort_values(by="Total Points", ascending=False).reset_index(drop=True)
        df_league.index += 1
        
        st.markdown("### 🥇 Top 3 Leaderboard")
        cols = st.columns(3)
        if len(df_league) >= 1: cols[0].metric("🥇 1st", f"{df_league.iloc[0]['Player']}", f"{df_league.iloc[0]['Total Points']} pts")
        if len(df_league) >= 2: cols[1].metric("🥈 2nd", f"{df_league.iloc[1]['Player']}", f"{df_league.iloc[1]['Total Points']} pts")
        if len(df_league) >= 3: cols[2].metric("🥉 3rd", f"{df_league.iloc[2]['Player']}", f"{df_league.iloc[2]['Total Points']} pts")
        
        st.write("---")
        st.markdown("### 📈 League Points Chart")
        chart_data = df_league.set_index("Player")["Total Points"]
        st.bar_chart(chart_data)
        
        st.write("---")
        display_df = df_league.drop(columns=["RawName"])
        st.dataframe(display_df, use_container_width=True)
    else:
        st.info("No overall standings recorded yet.")

if tab_season:
    with tab_season:
        st.subheader("⚙️ Session & Season Controls")
        
        with st.expander("🛠️ Emergency: Manually Add Missing Match", expanded=False):
            st.caption("Enter details below to add a missed match back to history.")
            
            with st.form("manual_match_form"):
                man_sess = st.number_input("Session Number", min_value=1, max_value=12, value=st.session_state.current_session_num)
                col_m1, col_m2 = st.columns(2)
                with col_m1:
                    t1_p1 = st.text_input("Team A P1").strip()
                    t1_p2 = st.text_input("Team A P2").strip()
                    score_a = st.number_input("Team A Score", min_value=0, max_value=30, value=21)
                with col_m2:
                    t2_p1 = st.text_input("Team B P1").strip()
                    t2_p2 = st.text_input("Team B P2").strip()
                    score_b = st.number_input("Team B Score", min_value=0, max_value=30, value=15)
                
                man_submit = st.form_submit_button("➕ Log Missing Match", use_container_width=True)
                if man_submit:
                    if t1_p1 and t1_p2 and t2_p1 and t2_p2:
                        t1 = [t1_p1, t1_p2]
                        t2 = [t2_p1, t2_p2]
                        log_match_to_database(man_sess, t1, t2, score_a, score_b)
                        st.success("Match successfully added!")
                    else:
                        st.error("Please fill in all player names.")

        st.write("---")
        st.markdown("### 🗑️ Recent Matches (Undo)")
        st.caption("Delete a recently saved match to reverse points.")
        recent_matches = fetch_permanent_match_history()[-10:]
        if recent_matches:
            for m in reversed(recent_matches):
                m_id = m['id']
                sess = m['session_num']
                t1 = " & ".join([get_player_display(x) for x in m.get('team_a', [])])
                t2 = " & ".join([get_player_display(x) for x in m.get('team_b', [])])
                s1, s2 = m.get('score_a', 0), m.get('score_b', 0)
                
                c1, c2 = st.columns([4, 1])
                c1.write(f"**ID {m_id}** | S{sess} | {t1} ({s1}) vs {t2} ({s2})")
                if c2.button("❌", key=f"del_m_{m_id}"):
                    try:
                        supabase.table("match_history_log").delete().eq("id", m_id).execute()
                        if sess == st.session_state.current_session_num:
                            for p in m.get('team_a', []):
                                if s1 > s2:
                                    st.session_state.session_scores[p] = max(0, st.session_state.session_scores.get(p, 0) - 2)
                                    st.session_state.league_standings[p] = max(0, st.session_state.league_standings.get(p, 0) - 2)
                                st.session_state.play_counts[p] = max(0, st.session_state.play_counts.get(p, 0) - 1)
                            for p in m.get('team_b', []):
                                if s2 > s1:
                                    st.session_state.session_scores[p] = max(0, st.session_state.session_scores.get(p, 0) - 2)
                                    st.session_state.league_standings[p] = max(0, st.session_state.league_standings.get(p, 0) - 2)
                                st.session_state.play_counts[p] = max(0, st.session_state.play_counts.get(p, 0) - 1)
                            save_global_session_state()
                        
                        st.success(f"Match {m_id} deleted!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
        else:
            st.info("No matches recorded yet.")

        st.write("---")
        st.markdown("### End Session / Season")
        if st.button("🏁 Complete Current Session", type="primary", use_container_width=True):
            current_live = fetch_live_courts()
            for c_num, c_match in current_live.items():
                if c_match:
                    process_court_finish_callback(c_num, c_match, f"c{c_num}_s1_pills", f"c{c_num}_s2_pills")
            if st.session_state.current_session_num < 12: st.session_state.current_session_num += 1
            st.session_state.active_players = []
            st.session_state.session_scores = {}
            st.session_state.play_counts = {}
            save_global_session_state()
            st.success(f"Advanced to Session {st.session_state.current_session_num} / 12.")
            st.rerun()

        if st.button("🔴 Reset Entire Season", use_container_width=True):
            st.session_state.current_session_num = 1
            st.session_state.league_standings = {}
            st.session_state.session_scores = {}
            st.session_state.active_players = {}
            st.session_state.play_counts = {}
            for c in range(1, 7): update_live_court(c, None, None)
            save_global_session_state()
            st.success("Season reset to Session 1!")
            st.rerun()

if tab_users:
    with tab_users:
        st.subheader("👥 User Logs & Active Presence")
        try:
            users_resp = supabase.table("users").select("*").execute()
            logs_resp = supabase.table("login_logs").select("username, login_time").order("id", desc=True).limit(50).execute()
            
            df_users = pd.DataFrame(users_resp.data) if users_resp.data else pd.DataFrame(columns=["username", "role", "created_at"])
            for col_to_drop in ["password", "rating"]:
                if col_to_drop in df_users.columns:
                    df_users = df_users.drop(columns=[col_to_drop])
                
            df_logs = pd.DataFrame(logs_resp.data) if logs_resp.data else pd.DataFrame(columns=["username", "login_time"])
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Players", len(df_users))
            c2.metric("Total Logins", len(df_logs))
            c3.metric("Online Now", len(active_viewers))
            
            st.write("---")
            st.markdown("### 🟢 Currently Viewing App")
            if active_viewers:
                st.write(", ".join([f"**{u}**" for u in active_viewers]))
            else:
                st.info("No active users browsing right now.")

            st.write("---")
            st.markdown("### 📋 Accounts")
            st.dataframe(df_users, use_container_width=True)
            st.write("---")
            st.markdown("### 🕒 Login Audit Trail")
            st.dataframe(df_logs, use_container_width=True)
        except Exception as ex:
            st.warning(f"Error: {ex}")
