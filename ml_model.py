import pandas as pd

def get_nearest_helpers():

    data = [
        {
            "Name": "Aarav",
            "Trust Score": 92,
            "Distance": 1.2,
            "Verified": "✅ Verified",
            "Avg Response Time": "3 min"
        },

        {
            "Name": "Priya",
            "Trust Score": 81,
            "Distance": 2.4,
            "Verified": "✅ Verified",
            "Avg Response Time": "5 min"
        },

        {
            "Name": "Kabir",
            "Trust Score": 67,
            "Distance": 3.8,
            "Verified": "Not Verified",
            "Avg Response Time": "7 min"
        },

        {
            "Name": "Riya",
            "Trust Score": 45,
            "Distance": 5.0,
            "Verified": "Not Verified",
            "Avg Response Time": "10 min"
        }
    ]

    return pd.DataFrame(data)