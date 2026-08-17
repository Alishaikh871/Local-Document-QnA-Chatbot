from functools import wraps
from flask import session, redirect, url_for

# ==========================================
# Demo Users
# ==========================================

USERS = {

    "admin": {
        "password": "password",
        "name": "Administrator"
    },

    "user": {
        "password": "123456",
        "name": "User"
    }

}


# ==========================================
# Authenticate User
# ==========================================

def authenticate(username, password):

    if username not in USERS:
        return None

    if USERS[username]["password"] != password:
        return None

    return USERS[username]


# ==========================================
# Login User
# ==========================================

def login_user(username):

    session["logged_in"] = True

    session["username"] = username

    session["name"] = USERS[username]["name"]


# ==========================================
# Logout User
# ==========================================

def logout_user():

    session.clear()


# ==========================================
# Check Login
# ==========================================

def is_logged_in():

    return session.get("logged_in", False)


# ==========================================
# Current User
# ==========================================

def current_user():

    if not is_logged_in():
        return None

    return {

        "username": session.get("username"),

        "name": session.get("name")

    }


# ==========================================
# Login Required Decorator
# ==========================================

def login_required(route_function):

    @wraps(route_function)

    def wrapper(*args, **kwargs):

        if not is_logged_in():

            return redirect(url_for("login"))

        return route_function(*args, **kwargs)

    return wrapper