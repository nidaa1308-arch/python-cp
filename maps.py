import sqlite3
import pandas as pd
import folium
from folium.plugins import HeatMap

DB_NAME = "trustcircle.db"


def build_map(sos_lat=None, sos_lng=None):
    """
    Builds the full TrustCircle map and saves it as trustcircle_map.html
    
    Parameters:
        sos_lat, sos_lng : if provided, adds a red SOS pin at that location
    """

    conn = sqlite3.connect(DB_NAME)

    # Load verified users with their trust scores
    users_df = pd.read_sql("""
        SELECT user_id, name, latitude, longitude, trust_score, is_verified
        FROM users
        WHERE is_verified = 1 AND is_active = 1
    """, conn)

    # Load zones from THEIR zones table
    zones_df = pd.read_sql("SELECT * FROM zones", conn)

    # Load police stations from THEIR table
    police_df = pd.read_sql("SELECT * FROM police_stations", conn)

    conn.close()

    print(f"✅ Loaded {len(users_df)} helpers, "
          f"{len(zones_df)} zones, {len(police_df)} police stations")

    # --- Create base map ---
    m = folium.Map(
        location=[18.52, 73.85],
        zoom_start=13,
        tiles="CartoDB positron"
    )

    # --- Draw zones (safe = green, unsafe = red) ---
    for _, zone in zones_df.iterrows():
        is_safe = zone["zone_type"] == "safe"
        color   = "green" if is_safe else "red"
        emoji   = "✅" if is_safe else "⚠️"
        label   = "Safe Zone" if is_safe else "Unsafe Zone"

        folium.Circle(
            location=[zone["latitude"], zone["longitude"]],
            radius=zone["radius_meters"],
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.2,
            tooltip=f"{emoji} {label}: {zone['zone_name']}"
        ).add_to(m)

    # --- Add police station markers ---
    for _, station in police_df.iterrows():
        folium.Marker(
            location=[station["latitude"], station["longitude"]],
            popup=folium.Popup(
                f"""
                <b>🚔 {station['name']}</b><br>
                📞 {station['phone']}<br>
                📍 {station['address']}
                """,
                max_width=220
            ),
            tooltip=f"🚔 {station['name']}",
            # A blue icon with a star = police station
            icon=folium.Icon(color="blue", icon="star")
        ).add_to(m)

    # --- Add helper markers (colored by trust score) ---
    for _, user in users_df.iterrows():
        # Skip users with no location set
        if user["latitude"] == 0.0 and user["longitude"] == 0.0:
            continue

        # Color based on trust score
        if user["trust_score"] >= 75:
            color = "green"
        elif user["trust_score"] >= 50:
            color = "orange"
        else:
            color = "red"

        verified_badge = "✅ Verified" if user["is_verified"] else "❌ Not Verified"

        folium.Marker(
            location=[user["latitude"], user["longitude"]],
            popup=folium.Popup(
                f"""
                <b>{user['name']}</b><br>
                Trust Score: <b>{user['trust_score']}</b><br>
                {verified_badge}
                """,
                max_width=180
            ),
            tooltip=f"{user['name']} — Score: {user['trust_score']}",
            icon=folium.Icon(color=color, icon="female", prefix="fa")
        ).add_to(m)

    # --- Add heatmap (shows helper density + trust) ---
    if not users_df.empty:
        heat_data = [
            [row["latitude"], row["longitude"], row["trust_score"] / 100]
            for _, row in users_df.iterrows()
            if not (row["latitude"] == 0.0 and row["longitude"] == 0.0)
        ]
        if heat_data:
            HeatMap(heat_data, radius=20).add_to(m)

    # --- Add SOS marker if location provided ---
    if sos_lat and sos_lng:
        folium.Marker(
            location=[sos_lat, sos_lng],
            popup="🆘 SOS Location",
            tooltip="SOS triggered here",
            icon=folium.Icon(color="red", icon="exclamation-sign")
        ).add_to(m)

    # --- Save the map ---
    m.save("trustcircle_map.html")
    print("✅ Map saved as trustcircle_map.html — open in browser!")
    return m


# Run directly to test
if __name__ == "__main__":
    print("=== TrustCircle Maps Module ===\n")

    # Build map with a fake SOS at Pune center
    build_map(sos_lat=18.52, sos_lng=73.85)
