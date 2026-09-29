import streamlit as st
import pandas as pd
import urllib.parse
from datetime import datetime
from zoneinfo import ZoneInfo
from supabase import create_client, Client
import time

st.set_page_config(page_title="Slough Badminton Club", page_icon="🏸", layout="wide")

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

# --- SUPABASE INIT ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

try:
    supabase: Client = init_supabase()
except Exception:
    st.error("Database connection failed. Verify Streamlit secrets.")

ADMIN_ACCOUNTS = {"admin": "4dm1n776&", "Musa": "4dmiN786&", "Simon": "4dm1nh3ll0", "Aaron": "A4dm1n1"}
DEFAULT_MASTER_ROSTER = ["Shoj", "Abdul Waheed", "Aaron", "Faisal", "Naveed", "AbdulKhader", "Ryan", "Abdullah sr", "Yousuf", "Aamer", "Mohsin", "Simon", "Joe S", "Hassan", "Habeeb"]

# --- DATABASE HELPERS ---
def load_master_player_list():
    try:
        resp = supabase.table("master_player_list").select("players").eq("id", 1).execute()
        return resp.data[0]["players"] if resp.data else DEFAULT_MASTER_ROSTER
    except Exception:
        return DEFAULT_MASTER_ROSTER

def save_master_player_list(players_list):
    try:
        supabase.table("master_player_list").upsert({"id": 1, "players": players_list}).execute()
        return True
    except Exception as e:
        st.error(f"Error saving roster: {e}")
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
        supabase.table("match_history_log").insert({"session_num": session_num, "team_a": team1, "team_b": team2, "score_a": s1, "score_b": s2}).execute()
    except Exception as e:
        st.error(f"Error logging match: {e}")

def fetch_live_courts():
    try:
        resp = supabase.table("live_courts").select("*").execute()
        courts = {}
        if resp.data:
            for row in resp.data:
                c_id = row["court_id"]
                courts[c_id] = {"team1": row["team_a"], "team2": row["team_b"]} if row.get("team_a") and row.get("team_b") else None
        return courts
    except Exception:
        return {}

def update_live_court(court_num, team1=None, team2=None):
    try:
        supabase.table("live_courts").upsert({"court_id": court_num, "team_a": team1, "team_b": team2}).execute()
    except Exception:
        pass

def update_user_presence(username):
    try:
        now_uk = datetime.now(ZoneInfo("Europe/London")).isoformat()
        supabase.table("active_presence").upsert({"username": username, "last_seen": now_uk}).execute()
    except Exception:
        pass

def get_active_viewers():
    try:
        now_utc = datetime.now(ZoneInfo("Europe/London"))
        resp = supabase.table("active_presence").select("username, last_seen").execute()
        active = []
        if resp.data:
            for row in resp.data:
                last_seen_dt = datetime.fromisoformat(row["last_seen"])
                if (now_utc - last_seen_dt).total_seconds() <= 180:
                    active.append(row["username"])
        return active
    except Exception:
        return []

def get_user_role(username, password):
    if username in ADMIN_ACCOUNTS and ADMIN_ACCOUNTS[username] == password: return "admin"
    try:
        resp = supabase.table("users").select("role").eq("username", username).eq("password", password).execute()
        if resp.data: return resp.data[0]["role"]
    except Exception:
        pass
    return None

def register_user(username, password):
    if username in ADMIN_ACCOUNTS: return False, "Username reserved."
    try:
        if supabase.table("users").select("username").eq("username", username).execute().data:
            return False, "Username already exists."
        supabase.table("users").insert({"username": username, "password": password, "role": "player"}).execute()
        return True, "Account created!"
    except Exception as e:
        return False, f"Error: {e}"

def log_login_event(username):
    try:
        now_uk = datetime.now(ZoneInfo("Europe/London")).strftime("%Y-%m-%d %H:%M:%S")
        supabase.table("login_logs").insert({"username": username, "login_time": now_uk}).execute()
    except Exception:
        pass

def is_open_access_window():
    now_uk = datetime.now(ZoneInfo("Europe/London"))
    # 0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday
    return now_uk.weekday() < 5 and (15 <= now_uk.hour < 22)

# --- SESSION INITIALIZATION ---
query_params = st.query_params
if "logged_in" not in st.session_state or not st.session_state.logged_in:
    if query_params.get("user") and query_params.get("role"):
        st.session_state.update({"logged_in": True, "username": query_params.get("user"), "role": query_params.get("role")})
    else:
        st.session_state.update({"logged_in": False, "username": None, "role": None})

if "last_court_time" not in st.session_state: st.session_state.last_court_time = {}
if "roster_builder" not in st.session_state: st.session_state.roster_builder = load_master_player_list()
if "live_ticker" not in st.session_state: st.session_state.live_ticker = ["👋 Welcome to Slough Badminton Club Mondays!"]

load_global_session_state()

if st.session_state.logged_in and st.session_state.username:
    update_user_presence(st.session_state.username)

RAW_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 260 260" width="260" height="260"><circle cx="130" cy="130" r="120" fill="#1E4867" stroke="#F9F8F3" stroke-width="6"/><path id="archPath" d="M 35,130 A 95,95 0 1,1 225,130" fill="none" /><text fill="#F9F8F3" font-size="15" font-weight="900" font-family="Arial, sans-serif" letter-spacing="2"><textPath href="#archPath" startOffset="50%" text-anchor="middle">BADMINTON MONDAYS</textPath></text><text x="130" y="145" font-size="44" text-anchor="middle">🏸</text><text x="130" y="172" font-size="13" fill="#F9F8F3" text-anchor="middle" letter-spacing="2">⭐⭐⭐⭐⭐</text><text x="130" y="195" font-size="11" font-weight="bold" fill="#F9F8F3" text-anchor="middle" font-family="Arial, sans-serif">8PM - 10PM</text><text x="130" y="212" font-size="11" font-weight="bold" fill="#F9F8F3" text-anchor="middle" font-family="Arial, sans-serif">DITTON PARK, SLOUGH</text></svg>"""
SVG_URL = "data:image/svg+xml;utf8," + urllib.parse.quote(RAW_SVG)

# --- LOGIN SCREEN ---
if not st.session_state.logged_in:
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        st.image(SVG_URL, width=160)
        st.title("Slough Badminton Club")
        login_tab, signup_tab = st.tabs(["🔒 Log In", "📝 Sign Up"])
        with login_tab:
            with st.form("login_form"):
                user_in = st.text_input("Username").strip()
                pass_in = st.text_input("Password", type="password").strip()
                if st.form_submit_button("Log In", use_container_width=True):
                    role = get_user_role(user_in, pass_in)
                    if role:
                        st.session_state.update({"logged_in": True, "username": user_in, "role": role})
                        st.query_params.update({"user": user_in, "role": role})
                        log_login_event(user_in)
                        st.rerun()
                    else:
                        st.error("Invalid credentials.")
        with signup_tab:
            with st.form("signup_form"):
                new_user = st.text_input("Choose Username").strip()
                new_pass = st.text_input("Choose Password", type="password").strip()
                conf_pass = st.text_input("Confirm Password", type="password").strip()
                if st.form_submit_button("Create Account", use_container_width=True):
                    if new_pass != conf_pass: st.error("Passwords do not match.")
                    elif not new_user or not new_pass: st.error("Fill in all fields.")
                    else:
                        success, msg = register_user(new_user, new_pass)
                        if success: st.success(msg)
                        else: st.error(msg)
    st.stop()

# --- MAIN APP LOGIC ---
open_access = is_open_access_window()
can_edit = open_access or (st.session_state.role == "admin")
is_master_admin = (st.session_state.username == "admin")
can_manage_season = (st.session_state.role == "admin") # Locked to admins only

st.sidebar.write(f"Logged in as: **{st.session_state.username}** ({st.session_state.role.capitalize()})")
st.sidebar.divider()

if is_master_admin:
    active_viewers = get_active_viewers()
    st.sidebar.markdown(f"🟢 **Online Right Now ({len(active_viewers)}):**")
    st.sidebar.caption(", ".join([f"**{u}**" for u in active_viewers]) if active_viewers else "No other active users.")
    st.sidebar.divider()

if st.session_state.role == "admin": 
    st.sidebar.success("👑 **Admin User: Full Access Active**")
elif open_access: 
    st.sidebar.success("🟢 **Admin Window Active (M-F 3PM-10PM)**")
else: 
    st.sidebar.info("🔒 **Outside Hours: Read-Only**")

if st.sidebar.button("Log Out", use_container_width=True):
    st.query_params.clear()
    st.session_state.update({"logged_in": False, "username": None, "role": None})
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

def get_resting_players(courts_state):
    playing = {p for match in courts_state.values() if match for p in match["team1"] + match["team2"]}
    resting = [p for p in st.session_state.active_players if p not in playing]
    return sorted(resting, key=lambda p: (st.session_state.play_counts.get(p, 0), st.session_state.last_court_time.get(p, 0)))

def assign_next_match_to_court(court_num, courts_state):
    resting = get_resting_players(courts_state)
    if len(resting) >= 4:
        next_4 = resting[:4]
        current_time = time.time()
        for p in next_4: 
            st.session_state.play_counts[p] = st.session_state.play_counts.get(p, 0) + 1
            st.session_state.last_court_time[p] = current_time 
        update_live_court(court_num, next_4[:2], next_4[2:])
        save_global_session_state()
        return True
    update_live_court(court_num, None, None)
    return False

def process_court_finish(court_num, match, s1_key, s2_key):
    s1, s2 = st.session_state.get(s1_key, 0), st.session_state.get(s2_key, 0)
    if s1 < 21 and s2 < 21: return ("error", f"⚠️ Court {court_num}: A team must reach 21!")
    if s1 == s2: return ("error", f"⚠️ Court {court_num}: Match cannot end in a draw!")
        
    log_match_to_database(st.session_state.current_session_num, match["team1"], match["team2"], s1, s2)
    win_score, lose_score = max(s1, s2), min(s1, s2)
    losing_team = match["team2"] if s1 > s2 else match["team1"]

    for p in match["team1"]:
        if s1 > s2:
            st.session_state.session_scores[p] = st.session_state.session_scores.get(p, 0) + 2
            st.session_state.league_standings[p] = st.session_state.league_standings.get(p, 0) + 2

    for p in match["team2"]:
        if s2 > s1:
            st.session_state.session_scores[p] = st.session_state.session_scores.get(p, 0) + 2
            st.session_state.league_standings[p] = st.session_state.league_standings.get(p, 0) + 2

    winner_str = f"{match['team1'][0]} & {match['team1'][1]}" if s1 > s2 else f"{match['team2'][0]} & {match['team2'][1]}"
    st.session_state.live_ticker.insert(0, f"🔥 Court {court_num}: {winner_str} won {win_score}-{lose_score} against {' & '.join(losing_team)}!")
    if len(st.session_state.live_ticker) > 5: st.session_state.live_ticker.pop()
    if abs(s1 - s2) <= 2: st.balloons()

    st.session_state.pop(s1_key, None)
    st.session_state.pop(s2_key, None)
    update_live_court(court_num, None, None)
    save_global_session_state()
    return ("success", f"Court {court_num} score saved!")

# --- COURTS TAB ---
if tab_courts:
    with tab_courts:
        if st.session_state.live_ticker:
            st.markdown(f'<div class="ticker-box">📢 <b>Broadcast:</b> {st.session_state.live_ticker[0]}</div>', unsafe_allow_html=True)
        if st.button("🔄 Refresh Courts", use_container_width=True): st.rerun()
            
        live_courts = fetch_live_courts()
        
        if not st.session_state.active_players:
            with st.container(border=True):
                st.subheader("👥 Session Setup")
                c_in, c_btn = st.columns([3, 1])
                new_p = c_in.text_input("Name", label_visibility="collapsed", key="quick_add")
                if c_btn.button("➕ Add", use_container_width=True) and new_p.strip():
                    if new_p.strip() not in st.session_state.roster_builder:
                        st.session_state.roster_builder.append(new_p.strip())
                    st.rerun()
                
                st.divider()
                for i, p in enumerate(list(st.session_state.roster_builder)):
                    c_n, c_d = st.columns([4, 1])
                    c_n.markdown(f"• **{p}**")
                    if c_d.button("❌", key=f"del_{i}"):
                        st.session_state.roster_builder.remove(p)
                        st.rerun()
                
                st.divider()
                if st.button("💾 Save Roster", use_container_width=True):
                    if save_master_player_list(st.session_state.roster_builder): st.success("Saved!")
                
                num_courts = st.number_input("Courts", 1, 6, 3)
                if st.button("🚀 Start Session", type="primary", use_container_width=True):
                    if len(st.session_state.roster_builder) < 4:
                        st.error("Need 4+ players.")
                    else:
                        st.session_state.active_players = list(st.session_state.roster_builder)
                        st.session_state.session_scores = {p: 0 for p in st.session_state.active_players}
                        st.session_state.play_counts = {p: 0 for p in st.session_state.active_players}
                        st.session_state.last_court_time = {p: 0 for p in st.session_state.active_players}
                        for c in range(1, num_courts + 1): update_live_court(c, None, None)
                        temp_courts = {}
                        for c in range(1, num_courts + 1):
                            assign_next_match_to_court(c, temp_courts)
                            temp_courts = fetch_live_courts()
                        save_global_session_state()
                        st.rerun()

        if st.session_state.active_players:
            with st.expander("👥 Manage Attendance"):
                c1, c2 = st.columns([3, 1])
                late_p = c1.text_input("Late Arrival", label_visibility="collapsed", key="late_add").strip()
                if c2.button("➕ Add", use_container_width=True) and late_p:
                    if late_p not in st.session_state.active_players:
                        st.session_state.active_players.append(late_p)
                        st.session_state.session_scores.setdefault(late_p, 0)
                        st.session_state.play_counts.setdefault(late_p, 0)
                        st.session_state.last_court_time.setdefault(late_p, 0)
                        st.session_state.league_standings.setdefault(late_p, 0)
                        save_global_session_state()
                        st.rerun()
                st.divider()
                for p in list(st.session_state.active_players):
                    c_p, c_rm = st.columns([4, 1])
                    c_p.write(f"• **{p}**")
                    if c_rm.button("❌", key=f"rm_{p}"):
                        st.session_state.active_players.remove(p)
                        save_global_session_state()
                        st.rerun()

            resting = get_resting_players(live_courts)
            st.info(f"⏸️ **Queue ({len(resting)}):** {', '.join(resting) or 'None'}")
            
            if st.button("💾 Save State to DB", use_container_width=True):
                save_global_session_state()
                st.success("State saved!")

            st.subheader("Live Courts")
            opts = list(range(31))
            for c_num in range(1, 4):
                match = live_courts.get(c_num)
                msg = st.session_state.pop(f"msg_{c_num}", None)
                if msg: st.error(msg[1]) if msg[0] == "error" else st.success(msg[1])

                with st.container(border=True):
                    st.markdown(f"#### 🏸 Court {c_num}")
                    if match:
                        st.caption("🔵 **Team A**")
                        st.write(f"• **{match['team1'][0]}** & **{match['team1'][1]}**")
                        st.pills("A Score", opts, 0, key=f"c{c_num}_s1", label_visibility="collapsed")
                        st.divider()
                        st.caption("🔴 **Team B**")
                        st.write(f"• **{match['team2'][0]}** & **{match['team2'][1]}**")
                        st.pills("B Score", opts, 0, key=f"c{c_num}_s2", label_visibility="collapsed")
                        if st.button(f"💾 Save & Finish", key=f"btn_{c_num}", type="primary", use_container_width=True):
                            res = process_court_finish(c_num, match, f"c{c_num}_s1", f"c{c_num}_s2")
                            st.session_state[f"msg_{c_num}"] = res
                            st.rerun()
                    else:
                        st.caption("No active match.")
                        if st.button(f"⚡ Start Match", key=f"start_{c_num}", use_container_width=True):
                            if not assign_next_match_to_court(c_num, live_courts): st.warning("Not enough players.")
                            st.rerun()

# --- STANDINGS ---
with tab_standings:
    st.subheader(f"Session {st.session_state.current_session_num} Standings")
    if st.session_state.session_scores:
        m_games = max(st.session_state.play_counts.values() or [0])
        m_pts = max(st.session_state.session_scores.values() or [0])
        data = []
        for p, pts in st.session_state.session_scores.items():
            g = st.session_state.play_counts.get(p, 0)
            b = []
            if g == m_games and g > 0: b.append("🏃‍♂️ Marathon")
            if pts == m_pts and pts > 0: b.append("⚡ Smasher")
            data.append({"Player": p, "Points": pts, "Games": g, "Badge": " · ".join(b) or "🔥 Contender"})
        df = pd.DataFrame(data).sort_values("Points", ascending=False).reset_index(drop=True)
        df.index += 1
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No games recorded.")

# --- HUB ---
with tab_hub:
    st.header("🔥 Hub & Rivalries")
    history = fetch_permanent_match_history()
    hist_p = {p for m in history for p in m.get("team_a", []) + m.get("team_b", [])}
    pool = sorted(list(set(st.session_state.get("active_players", [])).union(hist_p)) or DEFAULT_MASTER_ROSTER)
    
    if len(pool) >= 2:
        c1, c2 = st.columns(2)
        p1 = c1.selectbox("Player 1", pool, 0)
        p2 = c2.selectbox("Player 2", pool, 1)
        if p1 != p2:
            p1w, p2w, meet = 0, 0, 0
            for m in history:
                t1, t2 = m.get("team_a", []), m.get("team_b", [])
                s1, s2 = m.get("score_a", 0), m.get("score_b", 0)
                if (p1 in t1 and p2 in t2) or (p1 in t2 and p2 in t1):
                    meet += 1
                    if (p1 in t1 and s1 > s2) or (p1 in t2 and s2 > s1): p1w += 1
                    else: p2w += 1
            st.columns(3)[0].metric(f"{p1} Wins", p1w)
            st.columns(3)[1].metric("Battles", meet)
            st.columns(3)[2].metric(f"{p2} Wins", p2w)
        st.divider()
        tgt = st.selectbox("Form Guide", pool)
        form = ["🟢" if (tgt in m.get("team_a", []) and m.get("score_a",0)>m.get("score_b",0)) or (tgt in m.get("team_b", []) and m.get("score_b",0)>m.get("score_a",0)) else "🔴" for m in history if tgt in m.get("team_a", [])+m.get("team_b", [])]
        st.write(f"**Last 5:** {' '.join(form[-5:]) if form else 'No matches'}")

# --- RECAP ---
with tab_recap:
    st.header("Night Recap")
    hist = fetch_permanent_match_history()
    wins, pts, close = {}, {}, {}
    lng = {"s1": 0, "s2": 0}
    
    for m in hist:
        s1, s2 = m.get("score_a", 0), m.get("score_b", 0)
        t1, t2 = m.get("team_a", []), m.get("team_b", [])
        if s1 + s2 > lng["s1"] + lng["s2"]: lng = {"t1": t1, "t2": t2, "s1": s1, "s2": s2}
        is_c = abs(s1 - s2) <= 2
        for p in t1:
            pts[p] = pts.get(p, 0) + s1 + s2
            if is_c: close[p] = close.get(p, 0) + 1
            if s1 > s2: wins[p] = wins.get(p, 0) + 1
        for p in t2:
            pts[p] = pts.get(p, 0) + s1 + s2
            if is_c: close[p] = close.get(p, 0) + 1
            if s2 > s1: wins[p] = wins.get(p, 0) + 1
            
    st.caption(f"{len(hist)} total historical matches logged.")
    if hist:
        if wins:
            st.container(border=True).write(f"**CHAMPION**\n\n**{max(wins, key=wins.get)}** ({max(wins.values())} wins)")
        if lng.get("t1"):
            st.container(border=True).write(f"**LONGEST GAME**\n\n**{lng['s1']}–{lng['s2']}** ({' & '.join(lng['t1'])} vs {' & '.join(lng['t2'])})")
        if close:
            m_c = max(close.values())
            st.container(border=True).write(f"**CARDIAC KIDS**\n\n**{' · '.join([k for k, v in close.items() if v == m_c])}** ({m_c} close games)")
        if pts:
            st.container(border=True).write(f"**WORKHORSE**\n\n**{max(pts, key=pts.get)}** ({max(pts.values())} pts played)")

# --- LEAGUE ---
with tab_league:
    st.subheader(f"🏆 Overall League (Session {st.session_state.current_session_num}/12)")
    if st.session_state.league_standings:
        df_l = pd.DataFrame([{"Player": k, "Total Points": v} for k, v in st.session_state.league_standings.items()]).sort_values("Total Points", ascending=False).reset_index(drop=True)
        df_l.index += 1
        c = st.columns(3)
        if len(df_l) > 0: c[0].metric("🥇 1st", df_l.iloc[0]['Player'], df_l.iloc[0]['Total Points'])
        if len(df_l) > 1: c[1].metric("🥈 2nd", df_l.iloc[1]['Player'], df_l.iloc[1]['Total Points'])
        if len(df_l) > 2: c[2].metric("🥉 3rd", df_l.iloc[2]['Player'], df_l.iloc[2]['Total Points'])
        st.divider()
        st.bar_chart(df_l.set_index("Player")["Total Points"])
        st.dataframe(df_l, use_container_width=True)

# --- SEASON / ADMIN ---
if tab_season:
    with tab_season:
        st.subheader("⚙️ Settings")
        with st.expander("🛠️ Add Missing Match"):
            with st.form("man_match"):
                m_s = st.number_input("Session", 1, 12, st.session_state.current_session_num)
                c1, c2 = st.columns(2)
                t1p1, t1p2, sa = c1.text_input("A1"), c1.text_input("A2"), c1.number_input("A Score", 0, 30, 21)
                t2p1, t2p2, sb = c2.text_input("B1"), c2.text_input("B2"), c2.number_input("B Score", 0, 30, 15)
                if st.form_submit_button("➕ Log", use_container_width=True):
                    if all([t1p1, t1p2, t2p1, t2p2]):
                        log_match_to_database(m_s, [t1p1, t1p2], [t2p1, t2p2], sa, sb)
                        st.success("Added!")
                    else: st.error("Fill names.")

        st.divider()
        st.markdown("### 🗑️ Undo Matches")
        for m in reversed(fetch_permanent_match_history()[-10:]):
            mid, s_n = m['id'], m['session_num']
            t1, t2, s1, s2 = m.get('team_a',[]), m.get('team_b',[]), m.get('score_a',0), m.get('score_b',0)
            c_i, c_b = st.columns([4, 1])
            c_i.write(f"S{s_n} | {'&'.join(t1)} ({s1}) vs {'&'.join(t2)} ({s2})")
            if c_b.button("❌", key=f"del_{mid}"):
                supabase.table("match_history_log").delete().eq("id", mid).execute()
                if s_n == st.session_state.current_session_num:
                    for p in t1:
                        if s1 > s2:
                            st.session_state.session_scores[p] = max(0, st.session_state.session_scores.get(p,0)-2)
                            st.session_state.league_standings[p] = max(0, st.session_state.league_standings.get(p,0)-2)
                        st.session_state.play_counts[p] = max(0, st.session_state.play_counts.get(p,0)-1)
                    for p in t2:
                        if s2 > s1:
                            st.session_state.session_scores[p] = max(0, st.session_state.session_scores.get(p,0)-2)
                            st.session_state.league_standings[p] = max(0, st.session_state.league_standings.get(p,0)-2)
                        st.session_state.play_counts[p] = max(0, st.session_state.play_counts.get(p,0)-1)
                    save_global_session_state()
                st.rerun()

        st.divider()
        if st.button("🏁 End Current Session", type="primary", use_container_width=True):
            for c_num, m in fetch_live_courts().items():
                if m: process_court_finish(c_num, m, f"c{c_num}_s1", f"c{c_num}_s2")
            if st.session_state.current_session_num < 12: st.session_state.current_session_num += 1
            st.session_state.update({"active_players": [], "session_scores": {}, "play_counts": {}})
            save_global_session_state()
            st.rerun()

        if st.button("🔴 Reset Entire Season", use_container_width=True):
            st.session_state.update({"current_session_num": 1, "league_standings": {}, "session_scores": {}, "active_players": [], "play_counts": {}})
            for c in range(1, 7): update_live_court(c, None, None)
            save_global_session_state()
            st.rerun()

# --- USERS ---
if tab_users:
    with tab_users:
        st.subheader("👥 Database Logs")
        try:
            usr = supabase.table("users").select("username, role, created_at").execute().data or []
            log = supabase.table("login_logs").select("username, login_time").order("id", desc=True).limit(50).execute().data or []
            df_u, df_l = pd.DataFrame(usr), pd.DataFrame(log)
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Players", len(df_u))
            c2.metric("Logins", len(df_l))
            c3.metric("Online Now", len(active_viewers) if is_master_admin else "?")
            
            st.divider()
            st.dataframe(df_u, use_container_width=True)
            st.dataframe(df_l, use_container_width=True)
        except Exception as ex:
            st.warning(f"Error loading logs: {ex}")
