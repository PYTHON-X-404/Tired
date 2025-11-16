# -*- coding: utf-8 -*-
# --- PART 1/7 START ---

#!/usr/bin/env python3
from flask import Flask, request, redirect, session, render_template_string
import sqlite3, os, datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "supersecret"

# -------------- STATIC FOLDERS --------------
if not os.path.exists("static"):
    os.makedirs("static")
if not os.path.exists("static/photos"):
    os.makedirs("static/photos")
if not os.path.exists("static/posts"):
    os.makedirs("static/posts")

DB_PATH = "users.db"

# -------------- DB CONNECTION --------------
def get_db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# -------------- INIT DATABASE --------------
def init_db():
    conn = get_db_conn()
    c = conn.cursor()

    # USERS TABLE - Remove height column if exists
    c.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in c.fetchall()]
    
    if 'height' in columns:
        # Create temporary table without height
        c.execute("""
        CREATE TABLE users_new(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fullname TEXT,
            username TEXT UNIQUE,
            email TEXT UNIQUE,
            password TEXT,
            age TEXT,
            photo TEXT
        );
        """)
        
        # Copy data without height column
        c.execute("""
        INSERT INTO users_new (id, fullname, username, email, password, age, photo)
        SELECT id, fullname, username, email, password, age, photo FROM users
        """)
        
        # Drop old table and rename new one
        c.execute("DROP TABLE users")
        c.execute("ALTER TABLE users_new RENAME TO users")
    else:
        # Create fresh table
        c.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fullname TEXT,
            username TEXT UNIQUE,
            email TEXT UNIQUE,
            password TEXT,
            age TEXT,
            photo TEXT
        );
        """)

    # FOLLOWERS TABLE
    c.execute("""
    CREATE TABLE IF NOT EXISTS followers(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        follower_id INTEGER,
        UNIQUE(user_id, follower_id)
    );
    """)

    # POSTS TABLE
    c.execute("""
    CREATE TABLE IF NOT EXISTS posts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        caption TEXT,
        media TEXT,
        media_type TEXT,
        timestamp TEXT
    );
    """)

    # LIKES TABLE
    c.execute("""
    CREATE TABLE IF NOT EXISTS likes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER,
        user_id INTEGER,
        UNIQUE(post_id, user_id)
    );
    """)

    # COMMENTS TABLE
    c.execute("""
    CREATE TABLE IF NOT EXISTS comments(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER,
        user_id INTEGER,
        comment TEXT,
        timestamp TEXT
    );
    """)

    # MESSAGES TABLE — CHAT SYSTEM
    c.execute("""
    CREATE TABLE IF NOT EXISTS messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER,
        receiver_id INTEGER,
        message TEXT,
        timestamp TEXT
    );
    """)

    conn.commit()
    conn.close()


init_db()

# ----------- BASIC USER FUNCTIONS -----------
def fetch_user_by_username(username):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=?", (username,))
    user = c.fetchone()
    conn.close()
    return user


def fetch_user_by_id(uid):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (uid,))
    user = c.fetchone()
    conn.close()
    return user


def refresh_session_user():
    if "user" not in session:
        return
    username = session["user"][2]
    user = fetch_user_by_username(username)
    if user:
        session["user"] = tuple(user)


def followers_count(uid):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) AS cnt FROM followers WHERE user_id=?", (uid,))
    count = c.fetchone()["cnt"]
    conn.close()
    return count


def following_count(uid):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) AS cnt FROM followers WHERE follower_id=?", (uid,))
    count = c.fetchone()["cnt"]
    conn.close()
    return count


def is_following(target_id, visitor_id):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute(
        "SELECT 1 FROM followers WHERE user_id=? AND follower_id=?",
        (target_id, visitor_id),
    )
    r = c.fetchone()
    conn.close()
    return bool(r)


def detect_media_type(filename):
    ext = os.path.splitext(filename.lower())[1]
    if ext in (".mp4", ".mov", ".webm", ".mkv", ".ogg"):
        return "video"
    return "image"


def get_user_posts(uid):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM posts WHERE user_id=? ORDER BY datetime(timestamp) DESC",
        (uid,),
    )
    posts = c.fetchall()
    conn.close()
    return posts


def get_like_count(pid):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) AS cnt FROM likes WHERE post_id=?", (pid,))
    count = c.fetchone()["cnt"]
    conn.close()
    return count


def get_comment_count(pid):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) AS cnt FROM comments WHERE post_id=?", (pid,))
    count = c.fetchone()["cnt"]
    conn.close()
    return count


def is_liked(pid, uid):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT 1 FROM likes WHERE post_id=? AND user_id=?", (pid, uid))
    result = c.fetchone()
    conn.close()
    return bool(result)


def format_time(timestamp):
    try:
        dt = datetime.datetime.fromisoformat(timestamp)
        now = datetime.datetime.now()
        diff = now - dt
        if diff.days > 0:
            return f"{diff.days}d"
        elif diff.seconds > 3600:
            return f"{diff.seconds // 3600}h"
        elif diff.seconds > 60:
            return f"{diff.seconds // 60}m"
        else:
            return "now"
    except:
        return timestamp

# --- PART 1/7 END ---
# --- PART 2/7 START ---

# ---------------- GLOBAL CSS -----------------
momentum_css = """
<style>
    :root {
        --border-gray: #dbdbdb;
        --text-light: #737373;
        --bg-light: #fafafa;
        --btn-blue: #0095f6;
        --btn-hover: #1877f2;
        --red: #ed4956;
    }
    * {
        -webkit-user-select: none;
        -moz-user-select: none;
        -ms-user-select: none;
        user-select: none;
        -webkit-touch-callout: none;
        -webkit-tap-highlight-color: transparent;
    }
    html, body {
        margin: 0;
        padding: 0;
        width: 100%;
        height: 100%;
        overflow: hidden;
        position: fixed;
        font-family: Arial, sans-serif;
        background: var(--bg-light);
        touch-action: manipulation;
        -webkit-text-size-adjust: 100%;
        -ms-text-size-adjust: 100%;
        text-size-adjust: 100%;
    }
    body {
        zoom: 1;
        max-zoom: 1;
        min-zoom: 1;
    }
    .app-container {
        max-width: 100%;
        margin: 0 auto;
        padding: 15px;
        padding-top: 70px;
        padding-bottom: 70px;
        height: calc(100vh - 140px);
        overflow-y: auto;
        -webkit-overflow-scrolling: touch;
        box-sizing: border-box;
    }
    .btn {
        background: var(--btn-blue);
        padding: 12px 18px;
        color: white;
        border-radius: 8px;
        border: none;
        cursor: pointer;
        text-decoration: none;
        display: inline-block;
        font-size: 14px;
        font-weight: 600;
        text-align: center;
    }
    .btn:hover {
        background: var(--btn-hover);
    }
    .btn-outline {
        border: 1px solid var(--border-gray);
        padding: 12px 18px;
        border-radius: 8px;
        background: white;
        cursor: pointer;
        text-decoration: none;
        color: black;
        font-size: 14px;
        font-weight: 600;
        text-align: center;
    }
    .form-input {
        width: 100%;
        padding: 14px;
        margin-top: 8px;
        margin-bottom: 16px;
        border: 1px solid var(--border-gray);
        border-radius: 8px;
        box-sizing: border-box;
        font-size: 16px;
        background: white;
    }
    .file-input {
        width: 100%;
        padding: 14px;
        margin-top: 8px;
        margin-bottom: 16px;
        border: 2px dashed var(--border-gray);
        border-radius: 8px;
        box-sizing: border-box;
        font-size: 16px;
        background: #f8f9fa;
        text-align: center;
        cursor: pointer;
    }
    .file-input:hover {
        border-color: var(--btn-blue);
        background: #f0f8ff;
    }
    .nav-bar {
        height: 60px;
        border-bottom: 1px solid var(--border-gray);
        background: white;
        display: flex;
        justify-content: space-between;
        padding: 0 20px;
        align-items: center;
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        z-index: 1000;
        box-sizing: border-box;
    }
    .bottom-nav {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        height: 60px;
        background: white;
        border-top: 1px solid var(--border-gray);
        display: flex;
        justify-content: space-around;
        align-items: center;
        z-index: 1000;
        box-sizing: border-box;
    }
    .nav-icon {
        text-decoration: none;
        color: black;
        padding: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 8px;
    }
    .nav-icon.active {
        background: #f0f0f0;
    }
    .icon {
        width: 24px;
        height: 24px;
        fill: currentColor;
    }
    .welcome-container {
        max-width: 400px;
        margin: 100px auto;
        padding: 30px 20px;
        text-align: center;
        box-sizing: border-box;
    }
    .welcome-title {
        font-size: 32px;
        font-weight: bold;
        margin-bottom: 20px;
        color: #333;
    }
    .welcome-subtitle {
        color: #666;
        margin-bottom: 30px;
        line-height: 1.5;
        font-size: 16px;
    }
    .post-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 2px;
        margin-top: 20px;
    }
    .post-grid-item {
        aspect-ratio: 1;
        overflow: hidden;
        background: #f0f0f0;
    }
    .post-grid-item img,
    .post-grid-item video {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
    }
    .media-preview {
        width: 100%;
        max-height: 400px;
        object-fit: contain;
        background: #000;
        border-radius: 8px;
        margin-bottom: 15px;
    }
</style>
"""

# SVG ICONS
SVG_ICONS = {
    'home': '<svg class="icon" viewBox="0 0 24 24"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/></svg>',
    'search': '<svg class="icon" viewBox="0 0 24 24"><path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>',
    'add': '<svg class="icon" viewBox="0 0 24 24"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>',
    'message': '<svg class="icon" viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-1.99.9-1.99 2L2 22l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z"/></svg>',
    'profile': '<svg class="icon" viewBox="0 0 24 24"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>',
    'settings': '<svg class="icon" viewBox="0 0 24 24"><path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/></svg>',
    'heart': '<svg class="icon" viewBox="0 0 24 24"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>',
    'heart_outline': '<svg class="icon" viewBox="0 0 24 24"><path d="M16.5 3c-1.74 0-3.41.81-4.5 2.09C10.91 3.81 9.24 3 7.5 3 4.42 3 2 5.42 2 8.5c0 3.78 3.4 6.86 8.55 11.54L12 21.35l1.45-1.32C18.6 15.36 22 12.28 22 8.5 22 5.42 19.58 3 16.5 3zm-4.4 15.55l-.1.1-.1-.1C7.14 14.24 4 11.39 4 8.5 4 6.5 5.5 5 7.5 5c1.54 0 3.04.99 3.57 2.36h1.87C13.46 5.99 14.96 5 16.5 5c2 0 3.5 1.5 3.5 3.5 0 2.89-3.14 5.74-7.9 10.05z"/></svg>',
    'comment': '<svg class="icon" viewBox="0 0 24 24"><path d="M21 6h-2v9H6v2c0 .55.45 1 1 1h11l4 4V7c0-.55-.45-1-1-1zm-4 6V3c0-.55-.45-1-1-1H3c-.55 0-1 .45-1 1v14l4-4h11c.55 0 1-.45 1-1z"/></svg>'
}


# ---------------- HEADER FUNCTION -----------------
def get_header(user, current_page=""):
    # Use dictionary access instead of tuple unpacking to handle different user formats
    if isinstance(user, dict):
        username = user["username"]
    else:
        # Handle tuple format - try both 7 and 8 field versions
        try:
            if len(user) == 8:  # Old format with height
                uid, fullname, username, email, password, age, height, photo = user
            else:  # New format without height
                uid, fullname, username, email, password, age, photo = user
        except:
            # Fallback to index access
            username = user[2] if len(user) > 2 else "user"

    return f"""
    <div class='nav-bar'>
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <div style="font-size:22px; font-weight:700;">Momentum</div>
        <a class='nav-icon' href="/settings">{SVG_ICONS['settings']}</a>
    </div>
    """


# ---------------- BOTTOM NAV FUNCTION -----------------
def get_bottom_nav(user, current_page=""):
    # Use dictionary access instead of tuple unpacking
    if isinstance(user, dict):
        username = user["username"]
    else:
        # Handle tuple format - try both 7 and 8 field versions
        try:
            if len(user) == 8:  # Old format with height
                uid, fullname, username, email, password, age, height, photo = user
            else:  # New format without height
                uid, fullname, username, email, password, age, photo = user
        except:
            # Fallback to index access
            username = user[2] if len(user) > 2 else "user"
    
    home_active = "active" if current_page == "feed" else ""
    search_active = "active" if current_page == "search" else ""
    add_active = "active" if current_page == "create" else ""
    message_active = "active" if current_page == "direct" else ""
    profile_active = "active" if current_page == "profile" else ""
    
    return f"""
    <div class='bottom-nav'>
        <a class='nav-icon {home_active}' href="/feed">{SVG_ICONS['home']}</a>
        <a class='nav-icon {search_active}' href="/search">{SVG_ICONS['search']}</a>
        <a class='nav-icon {add_active}' href="/create">{SVG_ICONS['add']}</a>
        <a class='nav-icon {message_active}' href="/direct">{SVG_ICONS['message']}</a>
        <a class='nav-icon {profile_active}' href="/profile/{username}">{SVG_ICONS['profile']}</a>
    </div>
    """


# ================= AUTH ROUTES ===================

@app.route("/")
def home():
    if "user" in session:
        return redirect("/feed")
    return render_template_string(momentum_css + """
        <div class='welcome-container'>
            <div class='welcome-title'>Momentum</div>
            <div class='welcome-subtitle'>
                Connect with friends and share your moments. Join our community today 
                and start sharing your journey with the world.
            </div>
            
            <form method="POST" action="/login">
                <input class='form-input' name='username' placeholder='Username' required>
                <input class='form-input' name='password' placeholder='Password' type='password' required>
                <button class='btn' style='width:100%;'>Sign In</button>
            </form>

            <p style='margin-top:20px;'>
                Don't have an account? <a href="/register">Sign Up</a>
            </p>
        </div>
    """)


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", "")
    password = request.form.get("password", "")

    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    user = c.fetchone()
    conn.close()

    if user:
        session["user"] = tuple(user)
        return redirect("/feed")
    else:
        return "Invalid username or password!"


@app.route("/register")
def register():
    return render_template_string(momentum_css + """
        <div class='app-container' style='padding-top: 20px;'>
            <h2 style='text-align: center; margin-bottom: 30px;'>Create Your Account</h2>
            <form method="POST" enctype="multipart/form-data" action="/register_now">
                <input class='form-input' name='fullname' placeholder='Full Name' required>
                <input class='form-input' name='username' placeholder='Username' required>
                <input class='form-input' name='email' placeholder='Email' type='email' required>
                <input class='form-input' name='password' type='password' placeholder='Password' required>
                <input class='form-input' name='age' placeholder='Age' type='number' required>
                <label style='font-weight: bold; display: block; margin-bottom: 8px;'>Profile Photo</label>
                <input class='file-input' type='file' name='photo' accept='image/*' required>
                <button class='btn' style='width:100%; margin-top: 20px;'>Sign Up</button>
            </form>
        </div>
    """)


@app.route("/register_now", methods=["POST"])
def register_now():
    fullname = request.form["fullname"]
    username = request.form["username"]
    email = request.form["email"]
    password = request.form["password"]
    age = request.form["age"]

    file = request.files["photo"]
    filename = secure_filename(file.filename)
    file.save(os.path.join("static/photos", filename))

    conn = get_db_conn()
    c = conn.cursor()

    try:
        c.execute("""
            INSERT INTO users(fullname, username, email, password, age, photo)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (fullname, username, email, password, age, filename))
        conn.commit()
    except:
        conn.close()
        return "Username or Email already taken."

    conn.close()
    return redirect("/")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# --- PART 2/7 END ---
# --- PART 3/7 START ---

# ================= FEED PAGE ====================

@app.route("/feed")
def feed():
    if "user" not in session:
        return redirect("/")

    refresh_session_user()
    user = session["user"]
    uid = user[0] if isinstance(user, tuple) else user["id"]

    conn = get_db_conn()
    c = conn.cursor()

    # Fetch posts from user + followed users
    c.execute("""
        SELECT p.*, u.username, u.photo AS user_photo
        FROM posts p
        JOIN users u ON p.user_id = u.id
        WHERE p.user_id = ? OR p.user_id IN
              (SELECT user_id FROM followers WHERE follower_id=?)
        ORDER BY datetime(p.timestamp) DESC
    """, (uid, uid))

    posts = c.fetchall()
    conn.close()

    posts_html = ""

    for p in posts:
        like_count = get_like_count(p["id"])
        comment_count = get_comment_count(p["id"])
        is_liked_flag = is_liked(p["id"], uid)

        like_icon = SVG_ICONS['heart'] if is_liked_flag else SVG_ICONS['heart_outline']

        media_html = ""
        if p["media_type"] == "image":
            media_html = f"<img src='/static/posts/{p['media']}' style='width:100%; display: block;'>"
        else:
            media_html = f"<video src='/static/posts/{p['media']}' controls style='width:100%; display: block;'></video>"

        posts_html += f"""
        <div style='background:white; border:1px solid var(--border-gray); border-radius:12px; margin-bottom:20px; overflow: hidden;'>
            <div style='display:flex; align-items:center; padding:12px;'>
                <img src='/static/photos/{p['user_photo']}' style='width:40px;height:40px;border-radius:50%;margin-right:10px; object-fit: cover;'>
                <b><a href='/profile/{p['username']}' style='color:black; text-decoration:none;'>{p['username']}</a></b>
            </div>

            {media_html}

            <div style='padding:12px;'>

                <div style='display:flex; gap:12px; font-size:22px;'>
                    <a href='/like/{p["id"]}' style='text-decoration:none; color: {"#ed4956" if is_liked_flag else "black"};'>{like_icon}</a>
                    <a href='/post/{p["id"]}/comments' style='text-decoration:none; color: black;'>{SVG_ICONS['comment']}</a>
                </div>

                <p style='margin-top:5px; font-weight:bold;'>{like_count} likes</p>

                <p style='margin: 8px 0;'><b>{p['username']}</b> {p['caption']}</p>

                <a href='/post/{p["id"]}/comments' style='color:gray; text-decoration: none;'>View all {comment_count} comments</a>
            </div>
        </div>
        """

    html = momentum_css + get_header(session["user"], "feed") + f"""
        <div class='app-container'>
            {posts_html if posts_html else "<h3 style='text-align: center; color: #666;'>No posts yet. Follow people to see their posts!</h3>"}
        </div>
        """ + get_bottom_nav(session["user"], "feed")

    return render_template_string(html)



# ================= CREATE POST ====================

@app.route("/create")
def create():
    if "user" not in session:
        return redirect("/")
    return render_template_string(momentum_css + get_header(session["user"], "create") + """
        <div class='app-container'>
            <h2 style='text-align: center; margin-bottom: 30px;'>Create Post</h2>
            <form method='POST' enctype="multipart/form-data" action='/create_now'>
                <textarea class='form-input' name='caption' placeholder="Write a caption..." style='height: 100px; resize: vertical;'></textarea>
                <label style='font-weight: bold; display: block; margin-bottom: 8px;'>Select Media</label>
                <input class='file-input' type='file' name='media' accept='image/*,video/*' required>
                <button class='btn' style='width:100%; margin-top: 20px;'>Share Post</button>
            </form>
        </div>
        """ + get_bottom_nav(session["user"], "create"))


@app.route("/create_now", methods=["POST"])
def create_now():
    if "user" not in session:
        return redirect("/")

    uid = session["user"][0] if isinstance(session["user"], tuple) else session["user"]["id"]
    caption = request.form.get("caption", "")

    file = request.files["media"]
    filename = secure_filename(file.filename)
    file.save(os.path.join("static/posts", filename))

    media_type = detect_media_type(filename)
    timestamp = datetime.datetime.now().isoformat()

    conn = get_db_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO posts(user_id, caption, media, media_type, timestamp)
        VALUES (?, ?, ?, ?, ?)
    """, (uid, caption, filename, media_type, timestamp))
    conn.commit()
    conn.close()

    return redirect("/feed")



# ================= LIKE SYSTEM ====================

@app.route("/like/<pid>")
def like(pid):
    if "user" not in session:
        return redirect("/")
    uid = session["user"][0] if isinstance(session["user"], tuple) else session["user"]["id"]

    conn = get_db_conn()
    c = conn.cursor()

    if is_liked(pid, uid):
        c.execute("DELETE FROM likes WHERE post_id=? AND user_id=?", (pid, uid))
    else:
        c.execute("INSERT INTO likes(post_id, user_id) VALUES (?, ?)", (pid, uid))

    conn.commit()
    conn.close()
    return redirect("/feed")



# ================= COMMENT SYSTEM ====================

@app.route("/comment/<pid>", methods=["POST"])
def comment(pid):
    if "user" not in session:
        return redirect("/")
    uid = session["user"][0] if isinstance(session["user"], tuple) else session["user"]["id"]
    comment_text = request.form.get("comment", "").strip()

    if comment_text:
        ts = datetime.datetime.now().isoformat()
        conn = get_db_conn()
        c = conn.cursor()
        c.execute("""
            INSERT INTO comments(post_id, user_id, comment, timestamp)
            VALUES (?, ?, ?, ?)
        """, (pid, uid, comment_text, ts))
        conn.commit()
        conn.close()

    return redirect(f"/post/{pid}/comments")


# ================= VIEW SINGLE POST COMMENTS PAGE ===================

@app.route("/post/<pid>/comments")
def post_comments(pid):
    if "user" not in session:
        return redirect("/")

    uid = session["user"][0] if isinstance(session["user"], tuple) else session["user"]["id"]

    conn = get_db_conn()
    c = conn.cursor()

    # Fetch post
    c.execute("""
        SELECT p.*, u.username, u.photo AS user_photo
        FROM posts p 
        JOIN users u ON p.user_id = u.id
        WHERE p.id=?
    """, (pid,))
    post = c.fetchone()

    # Fetch comments
    c.execute("""
        SELECT c.*, u.username, u.photo AS user_photo
        FROM comments c
        JOIN users u ON c.user_id = u.id
        WHERE c.post_id=?
        ORDER BY datetime(c.timestamp)
    """, (pid,))
    comments = c.fetchall()

    conn.close()

    comments_html = ""
    for cm in comments:
        comments_html += f"""
        <div style='display:flex; gap:10px; padding:12px 0; border-bottom:1px solid #eee;'>
            <img src='/static/photos/{cm["user_photo"]}' style='width:36px;height:36px;border-radius:50%; object-fit: cover;'>
            <div style='flex: 1;'>
                <b>{cm["username"]}</b><br>
                <span style='color: #333;'>{cm["comment"]}</span>
            </div>
        </div>
        """

    media_html = ""
    if post["media_type"] == "image":
        media_html = f"<img src='/static/posts/{post['media']}' style='width:100%; border-radius: 8px;'>"
    else:
        media_html = f"<video src='/static/posts/{post['media']}' controls style='width:100%; border-radius: 8px;'></video>"

    html = momentum_css + get_header(session["user"]) + f"""
        <div class='app-container'>
            <div style="margin-bottom:20px;">
                <div style='display:flex; align-items:center; gap:10px; margin-bottom: 15px;'>
                    <img src='/static/photos/{post["user_photo"]}' style='width:40px;height:40px;border-radius:50%; object-fit: cover;'>
                    <b>{post["username"]}</b>
                </div>
                <div style="margin-top:10px;">{media_html}</div>
                <p style='margin: 12px 0;'><b>{post["username"]}</b> {post["caption"]}</p>
            </div>

            <h3 style='margin-bottom: 15px;'>Comments</h3>
            <div style='max-height: 300px; overflow-y: auto;'>
                {comments_html if comments_html else "<p style='text-align: center; color: #666;'>No comments yet</p>"}
            </div>

            <form method='POST' action='/comment/{pid}' style='margin-top:20px;'>
                <input name='comment' class='form-input' placeholder='Write a comment...' style='margin-bottom: 10px;'>
                <button class='btn' style='width: 100%;'>Post Comment</button>
            </form>
        </div>
        """ + get_bottom_nav(session["user"])

    return render_template_string(html)

# --- PART 3/7 END ---
# --- PART 4/7 START ---

# =================== SEARCH PAGE =====================

@app.route("/search", methods=["GET", "POST"])
def search():
    if "user" not in session:
        return redirect("/")

    query = ""

    results_html = ""

    if request.method == "POST":
        query = request.form.get("query", "").strip()

        conn = get_db_conn()
        c = conn.cursor()
        c.execute("""
            SELECT * FROM users 
            WHERE username LIKE ? OR fullname LIKE ?
        """, (f"%{query}%", f"%{query}%"))
        results = c.fetchall()
        conn.close()

        for u in results:
            results_html += f"""
            <a href='/profile/{u["username"]}' 
               style='display:flex; gap:12px; padding:12px; border-bottom:1px solid #eee; text-decoration:none; color:black; align-items: center;'>
                <img src='/static/photos/{u["photo"]}' 
                    style='width:50px; height:50px; border-radius:50%; object-fit: cover;'>
                <div>
                    <b style='display: block; margin-bottom: 4px;'>{u["username"]}</b>
                    <span style='color:gray; font-size:14px;'>{u["fullname"]}</span>
                </div>
            </a>
            """

    html = momentum_css + get_header(session["user"], "search") + f"""
        <div class='app-container'>
            <h2 style='margin-bottom: 20px;'>Search</h2>

            <form method='POST'>
                <input class='form-input' name='query' value='{query}' placeholder='Search users by username or name...'>
            </form>

            <div style='margin-top:20px; background: white; border-radius: 12px; overflow: hidden;'>
                {results_html if results_html else "<p style='text-align: center; padding: 30px; color: #666;'>No users found. Try searching with different terms.</p>"}
            </div>
        </div>
        """ + get_bottom_nav(session["user"], "search")

    return render_template_string(html)



# ================= FOLLOW USER =====================

@app.route("/follow/<tid>")
def follow(tid):
    if "user" not in session:
        return redirect("/")

    uid = session["user"][0] if isinstance(session["user"], tuple) else session["user"]["id"]

    conn = get_db_conn()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO followers(user_id, follower_id) VALUES (?, ?)", (tid, uid))
        conn.commit()
    except:
        pass

    conn.close()

    target = fetch_user_by_id(tid)
    return redirect(f"/profile/{target['username']}")


# ================= UNFOLLOW USER =====================

@app.route("/unfollow/<tid>")
def unfollow(tid):
    if "user" not in session:
        return redirect("/")

    uid = session["user"][0] if isinstance(session["user"], tuple) else session["user"]["id"]

    conn = get_db_conn()
    c = conn.cursor()
    c.execute("DELETE FROM followers WHERE user_id=? AND follower_id=?", (tid, uid))
    conn.commit()
    conn.close()

    target = fetch_user_by_id(tid)
    return redirect(f"/profile/{target['username']}")


# ================= PROFILE PAGE =====================

@app.route("/profile/<username>")
def profile(username):
    if "user" not in session:
        return redirect("/")

    viewer = session["user"]
    viewer_id = viewer[0] if isinstance(viewer, tuple) else viewer["id"]

    target = fetch_user_by_username(username)
    if not target:
        return "User not found."

    target_id = target["id"]

    # Follow Button Logic
    if viewer_id != target_id:
        if is_following(target_id, viewer_id):
            follow_btn = f"<a href='/unfollow/{target_id}' class='btn-outline'>Unfollow</a>"
        else:
            follow_btn = f"<a href='/follow/{target_id}' class='btn'>Follow</a>"
    else:
        follow_btn = ""

    # Post grid
    posts = get_user_posts(target_id)
    grid_html = ""
    for p in posts:
        if p["media_type"] == "image":
            grid_html += f"""
            <div class='post-grid-item'>
                <a href='/post/{p["id"]}/comments'>
                    <img src='/static/posts/{p["media"]}' alt='Post'>
                </a>
            </div>
            """
        else:
            grid_html += f"""
            <div class='post-grid-item'>
                <a href='/post/{p["id"]}/comments'>
                    <video src='/static/posts/{p["media"]}' style='object-fit: cover;'>
                </a>
            </div>
            """

    # FOLLOW / MESSAGE BUTTON + FULL NAME (Your request)
    action_buttons = ""
    if viewer_id != target_id:
        action_buttons = f"""
            <div style='display:flex; gap:12px; margin-top:10px;'>
                {follow_btn}
                <a href='/chat/{username}' class='btn' 
                   style='background:#0095F6; color:white;'>Message</a>
            </div>
        """

    html = momentum_css + get_header(session["user"], "profile") + f"""
        <div class='app-container'>

            <div style='display:flex; gap:20px; margin-top:20px; align-items:center;'>
                <img src='/static/photos/{target["photo"]}' 
                     style='width:90px; height:90px; border-radius:50%; object-fit:cover;'>

                <div style='flex: 1;'>
                    <h2 style='margin:0; padding:0; font-size: 24px;'>{target["fullname"]}</h2>
                    <p style='margin: 5px 0; color: #666;'>@{target["username"]}</p>
                    {action_buttons}
                </div>
            </div>

            <div style='display:flex; gap:25px; margin-top:20px; text-align: center;'>
                <div><b style='display: block; font-size: 18px;'>{len(posts)}</b><span style='color: #666;'>posts</span></div>
                <div><b style='display: block; font-size: 18px;'>{followers_count(target_id)}</b><span style='color: #666;'>followers</span></div>
                <div><b style='display: block; font-size: 18px;'>{following_count(target_id)}</b><span style='color: #666;'>following</span></div>
            </div>

            <hr style='margin:20px 0;'>

            <div class='post-grid'>
                {grid_html if grid_html else "<div style='grid-column: 1 / -1; text-align: center; padding: 40px; color: #666;'>No posts yet</div>"}
            </div>

        </div>
        """ + get_bottom_nav(session["user"], "profile")

    return render_template_string(html)

# --- PART 4/7 END ---
# --- PART 5/7 START ---

# ================= DIRECT MESSAGE (INBOX) =====================

@app.route("/direct")
def direct():
    if "user" not in session:
        return redirect("/")

    uid = session["user"][0] if isinstance(session["user"], tuple) else session["user"]["id"]

    conn = get_db_conn()
    c = conn.cursor()

    # fetch all chat partners (unique)
    c.execute("""
        SELECT DISTINCT
            CASE
                WHEN sender_id = ? THEN receiver_id
                ELSE sender_id
            END AS chat_user
        FROM messages
        WHERE sender_id = ? OR receiver_id = ?
    """, (uid, uid, uid))

    rows = c.fetchall()
    conn.close()

    chat_list_html = ""

    for r in rows:
        partner = fetch_user_by_id(r["chat_user"])
        chat_list_html += f"""
        <a href='/chat/{partner["username"]}' 
           style='display:flex; align-items:center; gap:12px; padding:15px;
                  border-bottom:1px solid #eee; text-decoration:none; color:black;'>
            <img src='/static/photos/{partner["photo"]}' 
                 style='width:50px; height:50px; border-radius:50%; object-fit:cover;'>
            <div>
                <b style='display: block; margin-bottom: 4px;'>{partner["username"]}</b>
                <span style='color:gray; font-size:14px;'>Tap to message</span>
            </div>
        </a>
        """

    html = momentum_css + get_header(session["user"], "direct") + f"""
        <div class='app-container'>
            <h2 style='margin-bottom: 20px;'>Messages</h2>
            <div style='margin-top:20px; background: white; border-radius: 12px; overflow: hidden;'>
                {chat_list_html if chat_list_html else "<p style='text-align: center; padding: 40px; color: #666;'>No messages yet. Start a conversation!</p>"}
            </div>
        </div>
        """ + get_bottom_nav(session["user"], "direct")

    return render_template_string(html)



# ================= CHAT WINDOW =====================

@app.route("/chat/<username>", methods=["GET", "POST"])
def chat(username):
    if "user" not in session:
        return redirect("/")

    sender_id = session["user"][0] if isinstance(session["user"], tuple) else session["user"]["id"]
    receiver = fetch_user_by_username(username)

    if not receiver:
        return "User does not exist."

    receiver_id = receiver["id"]

    # SEND MESSAGE
    if request.method == "POST":
        msg = request.form.get("message", "").strip()
        if msg:
            ts = datetime.datetime.now().isoformat()
            conn = get_db_conn()
            c = conn.cursor()
            c.execute("""
                INSERT INTO messages(sender_id, receiver_id, message, timestamp)
                VALUES (?, ?, ?, ?)
            """, (sender_id, receiver_id, msg, ts))
            conn.commit()
            conn.close()

        return redirect(f"/chat/{username}")

    # FETCH CHAT HISTORY
    conn = get_db_conn()
    c = conn.cursor()

    c.execute("""
        SELECT m.*, u.username, u.photo AS user_photo
        FROM messages m
        JOIN users u ON m.sender_id = u.id
        WHERE (sender_id=? AND receiver_id=?) OR 
              (sender_id=? AND receiver_id=?)
        ORDER BY datetime(timestamp)
    """, (sender_id, receiver_id, receiver_id, sender_id))

    msgs = c.fetchall()
    conn.close()

    # MESSAGE BUBBLES
    msgs_html = ""
    for m in msgs:
        align = "right" if m["sender_id"] == sender_id else "left"
        color = "#DCF8C6" if m["sender_id"] == sender_id else "#ffffff"

        msgs_html += f"""
        <div style='text-align:{align}; margin:8px 0;'>
            <div style='display:inline-block; padding:12px 16px;
                        background:{color};
                        border-radius:18px;
                        max-width:70%;
                        font-size:14px;
                        border:1px solid #e0e0e0;'>
                <b style='font-size:12px; color: #666;'>{m["username"]}</b><br>
                <span style='word-break: break-word;'>{m["message"]}</span>
            </div>
        </div>
        """

    html = momentum_css + get_header(session["user"]) + f"""
        <div style="position: fixed; top: 60px; left: 0; right: 0; bottom: 60px; background: white; display: flex; flex-direction: column;">
            <!-- CHAT HEADER -->
            <div style="display: flex; align-items: center; gap: 12px; padding: 15px; border-bottom: 1px solid #eee; background: white;">
                <img src='/static/photos/{receiver["photo"]}' 
                     style='width:45px; height:45px; border-radius:50%; object-fit:cover;'>
                <div>
                    <b style='font-size: 16px;'>{receiver["username"]}</b><br>
                    <span style='color:gray; font-size:12px;'>Active now</span>
                </div>
            </div>

            <!-- CHAT MESSAGES -->
            <div id='chatbox'
                 style='flex: 1; padding: 15px; overflow-y: auto; background: #f8f8f8;'>
                {msgs_html if msgs_html else '<div style="text-align: center; color: #666; padding: 40px;">No messages yet. Start the conversation!</div>'}
            </div>

            <!-- SEND FORM -->
            <form method='POST' style='padding: 15px; border-top: 1px solid #eee; background: white; display: flex; gap: 10px; align-items: center;'>
                <input name='message' style='flex: 1; padding: 12px 16px; border: 1px solid #ddd; border-radius: 24px; font-size: 16px;' 
                       placeholder='Type a message...' autocomplete='off'>
                <button class='btn' style='border-radius: 24px; padding: 12px 20px;'>Send</button>
            </form>
        </div>

        <!-- AUTO SCROLL TO BOTTOM -->
        <script>
            var box = document.getElementById('chatbox');
            box.scrollTop = box.scrollHeight;
        </script>
        """ + get_bottom_nav(session["user"])

    return render_template_string(html)

# --- PART 5/7 END ---
# --- PART 6/7 START ---

# ================= SETTINGS PAGE =====================

@app.route("/settings")
def settings():
    if "user" not in session:
        return redirect("/")

    html = momentum_css + get_header(session["user"]) + """
        <div class='app-container'>
            <h2 style='text-align: center; margin-bottom: 30px;'>Settings</h2>

            <a href='/edit_profile' class='btn' style='display:block; margin-top:15px; width:100%; text-align:center; padding: 15px;'>Edit Profile</a>
            <a href='/change_password' class='btn-outline' style='display:block; margin-top:15px; width:100%; text-align:center; padding: 15px;'>Change Password</a>
            <a href='/logout' class='btn-outline' style='display:block; margin-top:15px; color:red; border-color:red; width:100%; text-align:center; padding: 15px;'>Logout</a>
        </div>
        """ + get_bottom_nav(session["user"])

    return render_template_string(html)


# ================= EDIT PROFILE PAGE =====================

@app.route("/edit_profile", methods=["GET", "POST"])
def edit_profile():
    if "user" not in session:
        return redirect("/")

    user = fetch_user_by_id(session["user"][0] if isinstance(session["user"], tuple) else session["user"]["id"])

    if request.method == "POST":
        fullname = request.form.get("fullname", user["fullname"])
        email = request.form.get("email", user["email"])
        age = request.form.get("age", user["age"])

        photo_file = request.files.get("photo", None)
        filename = user["photo"]
        if photo_file and photo_file.filename:
            filename = secure_filename(photo_file.filename)
            photo_file.save(os.path.join("static/photos", filename))

        conn = get_db_conn()
        c = conn.cursor()
        c.execute("""
            UPDATE users 
            SET fullname=?, email=?, age=?, photo=?
            WHERE id=?
        """, (fullname, email, age, filename, user["id"]))
        conn.commit()
        conn.close()

        refresh_session_user()
        return redirect(f"/profile/{user['username']}")

    html = momentum_css + get_header(session["user"]) + f"""
        <div class='app-container'>
            <h2 style='text-align: center; margin-bottom: 30px;'>Edit Profile</h2>
            <form method='POST' enctype='multipart/form-data'>
                <label style='font-weight: bold; display: block; margin-bottom: 8px;'>Full Name</label>
                <input class='form-input' name='fullname' value='{user["fullname"]}'>
                <label style='font-weight: bold; display: block; margin-bottom: 8px;'>Email</label>
                <input class='form-input' name='email' value='{user["email"]}'>
                <label style='font-weight: bold; display: block; margin-bottom: 8px;'>Age</label>
                <input class='form-input' name='age' value='{user["age"]}'>
                <label style='font-weight: bold; display: block; margin-bottom: 8px;'>Profile Photo</label>
                <input class='file-input' type='file' name='photo' accept='image/*'>
                <button class='btn' style='width:100%; margin-top: 20px;'>Save Changes</button>
            </form>
        </div>
        """ + get_bottom_nav(session["user"])
    return render_template_string(html)


# ================= CHANGE PASSWORD =====================

@app.route("/change_password", methods=["GET", "POST"])
def change_password():
    if "user" not in session:
        return redirect("/")

    user = fetch_user_by_id(session["user"][0] if isinstance(session["user"], tuple) else session["user"]["id"])

    if request.method == "POST":
        old = request.form.get("old_password", "")
        new = request.form.get("new_password", "")

        if old != user["password"]:
            return "Old password incorrect!"

        conn = get_db_conn()
        c = conn.cursor()
        c.execute("UPDATE users SET password=? WHERE id=?", (new, user["id"]))
        conn.commit()
        conn.close()

        refresh_session_user()
        return redirect("/settings")

    html = momentum_css + get_header(session["user"]) + """
        <div class='app-container'>
            <h2 style='text-align: center; margin-bottom: 30px;'>Change Password</h2>
            <form method='POST'>
                <label style='font-weight: bold; display: block; margin-bottom: 8px;'>Old Password</label>
                <input class='form-input' type='password' name='old_password'>
                <label style='font-weight: bold; display: block; margin-bottom: 8px;'>New Password</label>
                <input class='form-input' type='password' name='new_password'>
                <button class='btn' style='width:100%; margin-top: 20px;'>Change Password</button>
            </form>
        </div>
        """ + get_bottom_nav(session["user"])
    return render_template_string(html)

# --- PART 6/7 END ---
# --- PART 7/7 START ---

# ========== ROOT REDIRECT ==========
@app.route("/home")
def goto_home():
    return redirect("/feed")


# ========== FLASK RUNNER ==========

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

# --- PART 7/7 END ---