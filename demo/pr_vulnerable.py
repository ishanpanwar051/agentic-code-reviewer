"""Demo File 2: Intentionally Vulnerable Code for PR Review Testing.

Expected Findings:
1. Security: SQL Injection via string formatting on line 22.
2. Security: Hardcoded JWT secret key on line 12.
3. Error Handling: Silent failure / bare except block swallowing errors on line 30.
4. Reliability: Unchecked None dereference causing AttributeError on line 37.
"""

import os
import sqlite3

# VULNERABILITY 1: Hardcoded Secret Key (AppSec Finding)
JWT_SECRET_KEY = "super_secret_jwt_token_key_12345!@#$"


def search_user(username: str, db_connection: sqlite3.Connection):
    # VULNERABILITY 2: SQL Injection via f-string interpolation
    query = f"SELECT * FROM users WHERE username = '{username}'"
    cursor = db_connection.cursor()
    cursor.execute(query)
    return cursor.fetchall()


def process_payment(account_id: str, amount: float):
    try:
        # Some critical payment transaction
        res = 100 / amount
    except:
        # VULNERABILITY 3: Silent exception swallowing (Error Handling Finding)
        pass


def get_user_profile(user_dict: dict | None):
    # VULNERABILITY 4: Unchecked None dereference (Reliability Bug)
    profile_name = user_dict.get("profile").upper()  # Crashes if user_dict is None or "profile" is None
    return profile_name
