import sqlite3
import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from sklearn.linear_model import LinearRegression
from geopy.distance import geodesic

# The database file everyone shares
DB_NAME = "trustcircle.db"


def load_data():
    """
    Load user data + their response history from the database.
    We JOIN two tables:
    - users         → basic info, location, current trust score
    - responses     → their SOS response history (accepted/ignored)
    
    A JOIN combines two tables like merging two Excel sheets on a common column.
    """
    conn = sqlite3.connect(DB_NAME)

    query = """
        SELECT
            u.user_id,
            u.name,
            u.latitude,
            u.longitude,
            u.is_verified,
            u.trust_score,

            -- COUNT counts how many responses this user has
            COUNT(r.response_id)                        AS total_responses,

            -- SUM counts only the 'accepted' responses
            SUM(CASE WHEN r.status = 'accepted' THEN 1 ELSE 0 END) AS accepted_count,

            -- AVG calculates average response time (NULL if no responses)
            AVG(r.response_time)                        AS avg_response_time

        FROM users u

        -- LEFT JOIN means: include ALL users, even if they have no responses
        LEFT JOIN responses r ON u.user_id = r.responder_id

        -- Only include verified, active users
        WHERE u.is_verified = 1

        -- GROUP BY is needed when using COUNT/SUM/AVG
        -- It means: calculate these numbers PER user
        GROUP BY u.user_id
    """

    df = pd.read_sql(query, conn)
    conn.close()

    print(f"✅ Loaded {len(df)} verified users from database")
    return df


def calculate_trust_scores(df):
    """
    Use ML to calculate a trust score for each user.
    Returns the dataframe with a new 'ml_trust_score' column.
    """

    # --- Feature Engineering ---
    # "Features" = the inputs we feed the ML model

    # success_rate = what % of responses were accepted
    # fillna(0) replaces empty values (users with no responses) with 0
    df["success_rate"] = (
        df["accepted_count"] / df["total_responses"]
    ).fillna(0)

    # For users with no response time recorded, assume a slow 15 mins
    df["avg_response_time"] = df["avg_response_time"].fillna(15.0)

    # For users with no responses at all, set count to 0
    df["total_responses"] = df["total_responses"].fillna(0)

    # These are the 4 things the model uses to judge trustworthiness
    features = [
        "total_responses",    # more responses = more active = more trustworthy
        "success_rate",       # higher success = more reliable
        "avg_response_time",  # lower time = faster = better
        "is_verified"         # verified users get a bonus
    ]

    X = df[features].copy()

    # --- Build a rule-based target score ---
    # The ML model needs to know what a "correct" score looks like
    # We define this with a formula (the model learns to match it)
    rule_score = (
        (df["total_responses"].clip(0, 20) / 20) * 30  +  # max 30 pts, capped at 20 responses
        df["success_rate"] * 40                         +  # max 40 pts
        (1 - df["avg_response_time"].clip(0,15) / 15) * 20 +  # max 20 pts
        df["is_verified"] * 10                             # 10 pts for verified
    ).clip(0, 100)

    # --- Scale the features ---
    # MinMaxScaler brings all numbers to the 0-1 range
    # So "total_responses=20" and "is_verified=1" are on the same scale
    scaler = MinMaxScaler()
    X_scaled = scaler.fit_transform(X)

    # --- Train the model ---
    model = LinearRegression()
    model.fit(X_scaled, rule_score)

    # --- Predict scores ---
    predicted = model.predict(X_scaled).clip(0, 100).round(1)
    df["ml_trust_score"] = predicted

    return df


def save_scores_to_db(df):
    """
    Save the ML-calculated trust scores back to the database.
    We use their update_trust_score function to also log the change
    in trust_history — so there's a full audit trail.
    """
    # Import their function so we use it the right way
    from database import update_trust_score

    print("\n--- Saving trust scores ---")
    for _, row in df.iterrows():
        success, msg = update_trust_score(
            user_id=int(row["user_id"]),
            new_score=float(row["ml_trust_score"]),
            reason="ML model recalculation"
        )
        print(f"  {row['name']}: {row['ml_trust_score']} — {msg}")


def get_nearest_helpers(sos_lat, sos_lng, top_n=3):
    """
    THIS IS THE KEY FUNCTION the frontend will call.
    
    Given an SOS location, returns the top N nearest helpers
    sorted by a combination of distance and trust score.
    
    Parameters:
        sos_lat  : latitude where SOS was triggered
        sos_lng  : longitude where SOS was triggered
        top_n    : how many helpers to return (default 3)
    
    Returns:
        A pandas DataFrame with columns:
        name, trust_score, distance_km, avg_response_time, is_verified
    """

    # Load all verified users from the database
    from database import get_all_verified_users
    users = get_all_verified_users()

    if not users:
        print("No verified users found in database")
        return pd.DataFrame()

    df = pd.DataFrame(users)

    # Calculate distance from SOS point to each helper
    # geodesic() calculates real-world distance on Earth's curved surface
    # It's more accurate than straight-line math
    sos_point = (sos_lat, sos_lng)

    def calculate_distance(row):
        helper_point = (row["latitude"], row["longitude"])
        # .km gives the distance in kilometers
        return geodesic(sos_point, helper_point).km

    df["distance_km"] = df.apply(calculate_distance, axis=1)
    df["distance_km"] = df["distance_km"].round(2)

    # Filter to only helpers within 10 km
    nearby = df[df["distance_km"] <= 10.0].copy()

    if nearby.empty:
        print("No helpers within 10 km — returning all users")
        nearby = df.copy()

    # Sort by: closest first, then highest trust score
    # ascending=[True, False] means: distance low→high, score high→low
    nearby = nearby.sort_values(
        by=["distance_km", "trust_score"],
        ascending=[True, False]
    )

    # Return only the columns the frontend needs
    result = nearby[[
        "user_id", "name", "trust_score",
        "distance_km", "latitude", "longitude"
    ]].head(top_n)

    return result


# --- Run this file directly to test everything ---
if __name__ == "__main__":
    print("=== TrustCircle ML Module ===\n")

    # 1. Load data
    df = load_data()

    # 2. Calculate scores
    df = calculate_trust_scores(df)

    # 3. Show results
    print("\n--- Trust Scores ---")
    print(df[["name", "total_responses", "success_rate",
              "avg_response_time", "is_verified", "ml_trust_score"]]
          .to_string(index=False))

    # 4. Save to database
    save_scores_to_db(df)

    # 5. Test get_nearest_helpers
    print("\n--- Testing get_nearest_helpers ---")
    print("SOS triggered at Pune center (18.52, 73.85)")
    helpers = get_nearest_helpers(18.52, 73.85, top_n=3)
    print(helpers.to_string(index=False))

    print("\n✅ Done! Trust scores saved to database.")
