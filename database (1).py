import sqlite3
import hashlib
import random
import re
from datetime import datetime, timedelta

DB_NAME = "trustcircle.db"


# --------------------------------------------------
# CONNECTION
# --------------------------------------------------

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


# --------------------------------------------------
# TABLE CREATION
# --------------------------------------------------

def create_tables():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            phone_number  TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_verified   INTEGER DEFAULT 0,
            otp_code      TEXT,
            otp_expiry    TEXT,
            latitude      REAL DEFAULT 0.0,
            longitude     REAL DEFAULT 0.0,
            trust_score   REAL DEFAULT 50.0,
            is_active     INTEGER DEFAULT 1,
            created_at    TEXT DEFAULT (datetime('now'))
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sos_events (
            sos_id        INTEGER PRIMARY KEY AUTOINCREMENT,
            triggered_by  INTEGER NOT NULL,
            latitude      REAL NOT NULL,
            longitude     REAL NOT NULL,
            status        TEXT DEFAULT 'active',
            triggered_at  TEXT DEFAULT (datetime('now')),
            resolved_at   TEXT,
            FOREIGN KEY (triggered_by) REFERENCES users(user_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS responses (
            response_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            sos_id        INTEGER NOT NULL,
            responder_id  INTEGER NOT NULL,
            response_time REAL,
            status        TEXT DEFAULT 'pending',
            responded_at  TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (sos_id)       REFERENCES sos_events(sos_id),
            FOREIGN KEY (responder_id) REFERENCES users(user_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trust_history (
            history_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            old_score   REAL,
            new_score   REAL,
            reason      TEXT,
            updated_at  TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS zones (
            zone_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            zone_name     TEXT NOT NULL,
            latitude      REAL NOT NULL,
            longitude     REAL NOT NULL,
            radius_meters REAL DEFAULT 500.0,
            zone_type     TEXT NOT NULL,
            created_at    TEXT DEFAULT (datetime('now'))
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS emergency_contacts (
            contact_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            contact_name  TEXT NOT NULL,
            contact_phone TEXT NOT NULL,
            relation      TEXT NOT NULL,
            created_at    TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS police_stations (
            station_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            latitude    REAL NOT NULL,
            longitude   REAL NOT NULL,
            phone       TEXT NOT NULL,
            address     TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS safe_walk_sessions (
            session_id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id           INTEGER NOT NULL,
            start_latitude    REAL NOT NULL,
            start_longitude   REAL NOT NULL,
            dest_latitude     REAL NOT NULL,
            dest_longitude    REAL NOT NULL,
            estimated_minutes INTEGER NOT NULL,
            checkin_interval  INTEGER DEFAULT 5,
            status            TEXT DEFAULT 'active',
            started_at        TEXT DEFAULT (datetime('now')),
            ended_at          TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS safe_walk_checkins (
            checkin_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id   INTEGER NOT NULL,
            latitude     REAL NOT NULL,
            longitude    REAL NOT NULL,
            checkin_time TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (session_id) REFERENCES safe_walk_sessions(session_id)
        )
    ''')

    conn.commit()
    conn.close()


# --------------------------------------------------
# VALIDATIONS
# --------------------------------------------------

def validate_phone(phone):
    phone = str(phone).strip()
    if not phone.isdigit():
        return False, "Phone number must contain digits only."
    if len(phone) != 10:
        return False, f"Phone number must be exactly 10 digits. Got {len(phone)}."
    if phone[0] not in ['6', '7', '8', '9']:
        return False, "Invalid Indian mobile number. Must start with 6, 7, 8, or 9."
    return True, "Valid."


def validate_name(name):
    name = name.strip()
    if not name:
        return False, "Name cannot be empty."
    if len(name) < 2:
        return False, "Name must be at least 2 characters."
    if len(name) > 50:
        return False, "Name cannot exceed 50 characters."
    if not re.match(r'^[A-Za-z\s]+$', name):
        return False, "Name can only contain letters and spaces."
    return True, "Valid."


def validate_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters."
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one digit."
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character."
    return True, "Valid."


def validate_otp(otp):
    otp = str(otp).strip()
    if not otp.isdigit():
        return False, "OTP must contain digits only."
    if len(otp) != 6:
        return False, f"OTP must be exactly 6 digits. Got {len(otp)}."
    return True, "Valid."


def validate_location(latitude, longitude):
    try:
        lat = float(latitude)
        lng = float(longitude)
    except (ValueError, TypeError):
        return False, "Latitude and longitude must be valid numbers."
    if not (-90 <= lat <= 90):
        return False, "Latitude must be between -90 and 90."
    if not (-180 <= lng <= 180):
        return False, "Longitude must be between -180 and 180."
    if not (8.0 <= lat <= 37.0 and 68.0 <= lng <= 97.0):
        return False, "Location appears to be outside India."
    return True, "Valid."


def validate_trust_score(score):
    try:
        s = float(score)
    except (ValueError, TypeError):
        return False, "Trust score must be a number."
    if not (0.0 <= s <= 100.0):
        return False, "Trust score must be between 0 and 100."
    return True, "Valid."


def validate_estimated_time(minutes):
    try:
        m = int(minutes)
    except (ValueError, TypeError):
        return False, "Estimated time must be a whole number."
    if not (1 <= m <= 180):
        return False, "Estimated time must be between 1 and 180 minutes."
    return True, "Valid."


def validate_checkin_interval(minutes):
    try:
        m = int(minutes)
    except (ValueError, TypeError):
        return False, "Check-in interval must be a whole number."
    if not (2 <= m <= 30):
        return False, "Check-in interval must be between 2 and 30 minutes."
    return True, "Valid."


# --------------------------------------------------
# USER FUNCTIONS
# --------------------------------------------------

def register_user(name, phone_number, password):
    valid, msg = validate_name(name)
    if not valid:
        return False, msg

    valid, msg = validate_phone(phone_number)
    if not valid:
        return False, msg

    valid, msg = validate_password(password)
    if not valid:
        return False, msg

    password_hash = hashlib.sha256(password.encode()).hexdigest()

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO users (name, phone_number, password_hash)
            VALUES (?, ?, ?)
        ''', (name.strip(), phone_number.strip(), password_hash))
        conn.commit()
        return True, "Registered successfully. OTP verification required."
    except sqlite3.IntegrityError:
        return False, "This phone number is already registered."
    finally:
        conn.close()


def update_location(user_id, latitude, longitude):
    valid, msg = validate_location(latitude, longitude)
    if not valid:
        return False, msg

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE users SET latitude = ?, longitude = ? WHERE user_id = ?',
        (float(latitude), float(longitude), user_id)
    )
    conn.commit()
    conn.close()
    return True, "Location updated."


def get_trust_score(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT trust_score FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row["trust_score"] if row else None


def update_trust_score(user_id, new_score, reason):
    valid, msg = validate_trust_score(new_score)
    if not valid:
        return False, msg

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT trust_score FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False, "User not found."

    old_score = row["trust_score"]
    cursor.execute(
        'UPDATE users SET trust_score = ? WHERE user_id = ?',
        (new_score, user_id)
    )
    cursor.execute('''
        INSERT INTO trust_history (user_id, old_score, new_score, reason)
        VALUES (?, ?, ?, ?)
    ''', (user_id, old_score, new_score, reason))
    conn.commit()
    conn.close()
    return True, "Trust score updated."


def get_all_verified_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT user_id, name, latitude, longitude, trust_score
        FROM users WHERE is_verified = 1 AND is_active = 1
    ''')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# --------------------------------------------------
# OTP FUNCTIONS
# --------------------------------------------------

def generate_otp(phone_number):
    valid, msg = validate_phone(phone_number)
    if not valid:
        return None, msg

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users WHERE phone_number = ?', (phone_number,))
    if not cursor.fetchone():
        conn.close()
        return None, "Phone number not registered."

    otp = str(random.randint(100000, 999999))
    expiry = (datetime.now() + timedelta(minutes=5)).isoformat()

    cursor.execute(
        'UPDATE users SET otp_code = ?, otp_expiry = ? WHERE phone_number = ?',
        (otp, expiry, phone_number)
    )
    conn.commit()
    conn.close()
    return otp, "OTP generated. Valid for 5 minutes."


def verify_otp(phone_number, entered_otp):
    valid, msg = validate_phone(phone_number)
    if not valid:
        return False, msg

    valid, msg = validate_otp(entered_otp)
    if not valid:
        return False, msg

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT otp_code, otp_expiry FROM users WHERE phone_number = ?',
        (phone_number,)
    )
    row = cursor.fetchone()

    if not row:
        conn.close()
        return False, "Phone number not found."
    if row["otp_code"] is None:
        conn.close()
        return False, "No OTP requested. Please generate a new one."
    if row["otp_code"] != str(entered_otp).strip():
        conn.close()
        return False, "Incorrect OTP."
    if datetime.now().isoformat() > row["otp_expiry"]:
        conn.close()
        return False, "OTP has expired. Please request a new one."

    cursor.execute('''
        UPDATE users
        SET is_verified = 1, otp_code = NULL, otp_expiry = NULL
        WHERE phone_number = ?
    ''', (phone_number,))
    conn.commit()
    conn.close()
    return True, "Phone number verified successfully."


# --------------------------------------------------
# SOS FUNCTIONS
# --------------------------------------------------

def trigger_sos(user_id, latitude, longitude):
    valid, msg = validate_location(latitude, longitude)
    if not valid:
        return None, msg

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT is_verified FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return None, "User not found."
    if not user["is_verified"]:
        conn.close()
        return None, "Phone number not verified. Cannot trigger SOS."

    cursor.execute('''
        INSERT INTO sos_events (triggered_by, latitude, longitude)
        VALUES (?, ?, ?)
    ''', (user_id, float(latitude), float(longitude)))
    sos_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return sos_id, "SOS triggered."


def log_response(sos_id, responder_id, response_time, status):
    if status not in ('accepted', 'ignored', 'pending'):
        return False, "Status must be accepted, ignored, or pending."

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO responses (sos_id, responder_id, response_time, status)
        VALUES (?, ?, ?, ?)
    ''', (sos_id, responder_id, response_time, status))
    conn.commit()
    conn.close()
    return True, "Response logged."


# --------------------------------------------------
# EMERGENCY CONTACT FUNCTIONS
# --------------------------------------------------

VALID_RELATIONS = ['mother', 'father', 'sister', 'brother', 'friend', 'husband', 'other']


def add_emergency_contact(user_id, contact_name, contact_phone, relation):
    valid, msg = validate_name(contact_name)
    if not valid:
        return False, f"Contact name invalid: {msg}"

    valid, msg = validate_phone(contact_phone)
    if not valid:
        return False, f"Contact phone invalid: {msg}"

    if relation.lower() not in VALID_RELATIONS:
        return False, f"Relation must be one of: {', '.join(VALID_RELATIONS)}."

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        'SELECT COUNT(*) as count FROM emergency_contacts WHERE user_id = ?',
        (user_id,)
    )
    if cursor.fetchone()["count"] >= 3:
        conn.close()
        return False, "Maximum 3 emergency contacts allowed."

    cursor.execute(
        'SELECT contact_id FROM emergency_contacts WHERE user_id = ? AND contact_phone = ?',
        (user_id, contact_phone)
    )
    if cursor.fetchone():
        conn.close()
        return False, "This phone number is already added as an emergency contact."

    cursor.execute('''
        INSERT INTO emergency_contacts (user_id, contact_name, contact_phone, relation)
        VALUES (?, ?, ?, ?)
    ''', (user_id, contact_name.strip(), contact_phone.strip(), relation.lower()))
    conn.commit()
    conn.close()
    return True, "Emergency contact added."


def get_emergency_contacts(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT contact_name, contact_phone, relation
        FROM emergency_contacts WHERE user_id = ?
    ''', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def remove_emergency_contact(user_id, contact_phone):
    valid, msg = validate_phone(contact_phone)
    if not valid:
        return False, msg

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        DELETE FROM emergency_contacts
        WHERE user_id = ? AND contact_phone = ?
    ''', (user_id, contact_phone))
    conn.commit()
    affected = cursor.rowcount
    conn.close()

    if affected == 0:
        return False, "Contact not found."
    return True, "Emergency contact removed."


# --------------------------------------------------
# POLICE STATION FUNCTIONS
# --------------------------------------------------

def seed_pune_police_stations():
    stations = [
        ("Shivajinagar Police Station",    18.5308, 73.8474, "02025536312", "Shivajinagar, Pune"),
        ("Deccan Gymkhana Police Station", 18.5162, 73.8401, "02025654321", "Deccan Gymkhana, Pune"),
        ("Swargate Police Station",        18.5018, 73.8567, "02024441234", "Swargate, Pune"),
        ("Hadapsar Police Station",        18.5018, 73.9260, "02026872345", "Hadapsar, Pune"),
        ("Kothrud Police Station",         18.5074, 73.8077, "02025382222", "Kothrud, Pune"),
        ("Viman Nagar Police Station",     18.5679, 73.9143, "02026633456", "Viman Nagar, Pune"),
        ("Yerawada Police Station",        18.5537, 73.8936, "02026685678", "Yerawada, Pune"),
        ("Kondhwa Police Station",         18.4647, 73.8862, "02026831234", "Kondhwa, Pune"),
        ("Pimpri Police Station",          18.6279, 73.7997, "02027427890", "Pimpri, Pune"),
        ("Chinchwad Police Station",       18.6440, 73.7930, "02027474567", "Chinchwad, Pune"),
    ]

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) as count FROM police_stations')
    if cursor.fetchone()["count"] > 0:
        conn.close()
        return False, "Police stations already seeded."

    cursor.executemany('''
        INSERT INTO police_stations (name, latitude, longitude, phone, address)
        VALUES (?, ?, ?, ?, ?)
    ''', stations)
    conn.commit()
    conn.close()
    return True, f"{len(stations)} police stations added."


def get_nearest_police_station(latitude, longitude):
    valid, msg = validate_location(latitude, longitude)
    if not valid:
        return None, msg

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM police_stations')
    stations = [dict(row) for row in cursor.fetchall()]
    conn.close()

    if not stations:
        return None, "No police stations in database."

    lat = float(latitude)
    lng = float(longitude)

    def rough_distance(s):
        return ((s["latitude"] - lat) ** 2 + (s["longitude"] - lng) ** 2) ** 0.5

    nearest = min(stations, key=rough_distance)
    return nearest, "Nearest station found."


def get_all_police_stations():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM police_stations')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# --------------------------------------------------
# SAFE WALK FUNCTIONS
# --------------------------------------------------

def start_safe_walk(user_id, start_lat, start_lng, dest_lat, dest_lng,
                    estimated_minutes, checkin_interval=5):
    valid, msg = validate_location(start_lat, start_lng)
    if not valid:
        return None, f"Start location invalid: {msg}"

    valid, msg = validate_location(dest_lat, dest_lng)
    if not valid:
        return None, f"Destination invalid: {msg}"

    valid, msg = validate_estimated_time(estimated_minutes)
    if not valid:
        return None, msg

    valid, msg = validate_checkin_interval(checkin_interval)
    if not valid:
        return None, msg

    if int(checkin_interval) >= int(estimated_minutes):
        return None, "Check-in interval must be less than estimated travel time."

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT is_verified FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return None, "User not found."
    if not user["is_verified"]:
        conn.close()
        return None, "Phone number not verified. Cannot start Safe Walk."

    cursor.execute('''
        SELECT session_id FROM safe_walk_sessions
        WHERE user_id = ? AND status = 'active'
    ''', (user_id,))
    if cursor.fetchone():
        conn.close()
        return None, "A Safe Walk session is already active. End it before starting a new one."

    cursor.execute('''
        INSERT INTO safe_walk_sessions
        (user_id, start_latitude, start_longitude, dest_latitude, dest_longitude,
         estimated_minutes, checkin_interval)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, float(start_lat), float(start_lng),
          float(dest_lat), float(dest_lng),
          int(estimated_minutes), int(checkin_interval)))

    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return session_id, "Safe Walk started."


def safe_walk_checkin(session_id, latitude, longitude):
    valid, msg = validate_location(latitude, longitude)
    if not valid:
        return False, msg

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT status FROM safe_walk_sessions WHERE session_id = ?',
        (session_id,)
    )
    session = cursor.fetchone()

    if not session:
        conn.close()
        return False, "Session not found."
    if session["status"] != "active":
        conn.close()
        return False, "Session is no longer active."

    cursor.execute('''
        INSERT INTO safe_walk_checkins (session_id, latitude, longitude)
        VALUES (?, ?, ?)
    ''', (session_id, float(latitude), float(longitude)))
    conn.commit()
    conn.close()
    return True, "Check-in recorded. Stay safe."


def end_safe_walk(session_id, user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT status, user_id FROM safe_walk_sessions WHERE session_id = ?',
        (session_id,)
    )
    session = cursor.fetchone()

    if not session:
        conn.close()
        return False, "Session not found."
    if session["user_id"] != user_id:
        conn.close()
        return False, "Unauthorized. This session does not belong to you."
    if session["status"] != "active":
        conn.close()
        return False, "Session is already ended."

    cursor.execute('''
        UPDATE safe_walk_sessions
        SET status = 'completed', ended_at = ?
        WHERE session_id = ?
    ''', (datetime.now().isoformat(), session_id))
    conn.commit()
    conn.close()
    return True, "Safe Walk ended. Glad you are safe."


def get_active_safe_walk(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM safe_walk_sessions
        WHERE user_id = ? AND status = 'active'
    ''', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_safe_walk_checkins(session_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT latitude, longitude, checkin_time
        FROM safe_walk_checkins WHERE session_id = ?
        ORDER BY checkin_time ASC
    ''', (session_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def mark_safe_walk_sos(session_id):
    """Called by Manas APScheduler when check-in is missed."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE safe_walk_sessions
        SET status = 'sos_triggered', ended_at = ?
        WHERE session_id = ? AND status = 'active'
    ''', (datetime.now().isoformat(), session_id))
    conn.commit()
    affected = cursor.rowcount
    conn.close()

    if affected == 0:
        return False, "Session not found or already ended."
    return True, "Session marked as SOS triggered."


# --------------------------------------------------
# ENTRY POINT
# --------------------------------------------------

if __name__ == "__main__":
    create_tables()

    # Registration
    print(register_user("Nida", "9876543210", "Password1!"))
    print(register_user("", "9876543210", "Password1!"))        # invalid name
    print(register_user("Nida", "12345", "Password1!"))         # invalid phone
    print(register_user("Nida", "9876543210", "weakpass"))      # weak password

    # OTP
    otp, msg = generate_otp("9876543210")
    print(msg)
    print(verify_otp("9876543210", "000000"))                   # wrong OTP
    print(verify_otp("9876543210", otp))                        # correct OTP

    # SOS
    print(trigger_sos(1, 18.5204, 73.8567))

    # Emergency contacts
    print(add_emergency_contact(1, "Ammi", "9123456780", "mother"))
    print(add_emergency_contact(1, "Sister", "9123456781", "sister"))
    print(add_emergency_contact(1, "Ammi", "9123456780", "mother"))   # duplicate
    print(get_emergency_contacts(1))

    # Police stations
    print(seed_pune_police_stations())
    station, msg = get_nearest_police_station(18.5204, 73.8567)
    print(msg, station)

    # Safe Walk
    session_id, msg = start_safe_walk(1, 18.5204, 73.8567, 18.5314, 73.8446, 20, 5)
    print(msg, "| Session ID:", session_id)
    print(start_safe_walk(1, 18.5204, 73.8567, 18.5314, 73.8446, 20, 5))  # duplicate session
    print(safe_walk_checkin(session_id, 18.5230, 73.8500))
    print(get_safe_walk_checkins(session_id))
    print(end_safe_walk(session_id, 1))
    print(end_safe_walk(session_id, 1))                                    # already ended
