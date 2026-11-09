
from flask import Flask, jsonify, render_template, request
from pathlib import Path
import sqlite3
from datetime import datetime, timezone

app = Flask(__name__)
DB = Path("data/miniboard.db")

# リアクションの種類
REACTIONS = ["👍", "❤️", "😂", "🔥"]

def connect():
    DB.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with connect() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")

        # リアクションを保存するテーブル
        con.execute("""CREATE TABLE IF NOT EXISTS reactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            reaction TEXT NOT NULL,
            FOREIGN KEY(message_id) REFERENCES messages(id)
        )""")

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/api/messages")
def get_messages():
    with connect() as con:
        rows = con.execute("SELECT * FROM messages ORDER BY id DESC").fetchall()
        messages = []

        for row in rows:
            data = dict(row)
            counts = con.execute(
                "SELECT reaction, COUNT(*) AS count FROM reactions "
                "WHERE message_id=? GROUP BY reaction",
                (row["id"],)
            ).fetchall()

            data["reactions"] = {r["reaction"]: r["count"] for r in counts}
            messages.append(data)

    return jsonify(messages)

@app.post("/api/messages")
def create_message():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()[:30]
    message = str(data.get("message", "")).strip()[:300]

    if not name or not message:
        return jsonify({"error": "name and message are required"}), 400

    created_at = datetime.now(timezone.utc).isoformat()

    with connect() as con:
        cur = con.execute(
            "INSERT INTO messages(name,message,created_at) VALUES(?,?,?)",
            (name, message, created_at)
        )
        row = con.execute(
            "SELECT * FROM messages WHERE id=?",
            (cur.lastrowid,)
        ).fetchone()

    return jsonify(dict(row)), 201

# リアクションの追加・取り消し
@app.post("/api/messages/<int:message_id>/reactions")
def toggle_reaction(message_id):
    data = request.get_json(silent=True) or {}
    reaction = data.get("reaction")

    if reaction not in REACTIONS:
        return jsonify({"error": "invalid reaction"}), 400

    with connect() as con:
        message = con.execute(
            "SELECT id FROM messages WHERE id=?", (message_id,)
        ).fetchone()

        if message is None:
            return jsonify({"error": "not found"}), 404

        # 同じリアクションがあれば取り消す
        existing = con.execute(
            "SELECT id FROM reactions WHERE message_id=? AND reaction=? LIMIT 1",
            (message_id, reaction)
        ).fetchone()

        if existing:
            con.execute("DELETE FROM reactions WHERE id=?", (existing["id"],))
            action = "removed"
        else:
            con.execute(
                "INSERT INTO reactions(message_id,reaction) VALUES(?,?)",
                (message_id, reaction)
            )
            action = "added"

        counts = con.execute(
            "SELECT reaction, COUNT(*) AS count FROM reactions "
            "WHERE message_id=? GROUP BY reaction",
            (message_id,)
        ).fetchall()

    return jsonify({
        "action": action,
        "reactions": {r["reaction"]: r["count"] for r in counts}
    })

@app.put("/api/messages/<int:message_id>")
def update_message(message_id):
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()[:300]

    if not message:
        return jsonify({"error": "message is required"}), 400

    with connect() as con:
        cur = con.execute(
            "UPDATE messages SET message=? WHERE id=?",
            (message, message_id)
        )
        if cur.rowcount == 0:
            return jsonify({"error": "not found"}), 404

    return jsonify({"ok": True})

@app.delete("/api/messages/<int:message_id>")
def delete_message(message_id):
    with connect() as con:
        con.execute(
            "DELETE FROM reactions WHERE message_id=?", (message_id,)
        )
        cur = con.execute(
            "DELETE FROM messages WHERE id=?", (message_id,)
        )

        if cur.rowcount == 0:
            return jsonify({"error": "not found"}), 404

    return "", 204

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=False)
