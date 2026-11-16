
from flask import Flask, jsonify, render_template, request
from pathlib import Path
import sqlite3
from datetime import datetime, timezone
from werkzeug.utils import secure_filename
from uuid import uuid4

app = Flask(__name__)
DB = Path("data/miniboard.db")

UPLOAD_FOLDER = Path("static/uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

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

        # 商品情報を保存するテーブル
        con.execute("""CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            description TEXT NOT NULL,
            image TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")

        con.execute("""CREATE TABLE IF NOT EXISTS product_reactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            reaction TEXT NOT NULL,
            FOREIGN KEY(product_id) REFERENCES products(id)
        )""")

        # 購入された商品と注文内容を保存するテーブル
        con.execute("""CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL UNIQUE,
            product_name TEXT NOT NULL,
            price INTEGER NOT NULL,
            buyer_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(product_id) REFERENCES products(id)
        )""")

        con.execute("""CREATE TABLE IF NOT EXISTS product_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            comment TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(product_id) REFERENCES products(id)
        )""")


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/messages")
def get_messages():
    with connect() as con:
        rows = con.execute(
            "SELECT * FROM messages ORDER BY id DESC"
        ).fetchall()
        messages = []

        for row in rows:
            data = dict(row)
            counts = con.execute(
                "SELECT reaction, COUNT(*) AS count FROM reactions "
                "WHERE message_id=? GROUP BY reaction",
                (row["id"],)
            ).fetchall()

            data["reactions"] = {
                r["reaction"]: r["count"] for r in counts
            }
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

        existing = con.execute(
            "SELECT id FROM reactions WHERE message_id=? AND reaction=? LIMIT 1",
            (message_id, reaction)
        ).fetchone()

        if existing:
            con.execute(
                "DELETE FROM reactions WHERE id=?", (existing["id"],)
            )
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


# 商品一覧を取得
@app.get("/api/products")
def get_products():
    with connect() as con:
        rows = con.execute(
            """SELECT products.*,
            EXISTS(
                SELECT 1 FROM orders WHERE orders.product_id=products.id
            ) AS sold
            FROM products ORDER BY id DESC"""
        ).fetchall()
        products = []

        for row in rows:
            data = dict(row)
            counts = con.execute(
                "SELECT reaction, COUNT(*) AS count FROM product_reactions "
                "WHERE product_id=? GROUP BY reaction",
                (row["id"],)
            ).fetchall()
            data["reactions"] = {
                r["reaction"]: r["count"] for r in counts
            }
            products.append(data)

    return jsonify(products)


@app.get("/api/products/<int:product_id>/comments")
def get_product_comments(product_id):
    with connect() as con:
        product = con.execute(
            "SELECT id FROM products WHERE id=?", (product_id,)
        ).fetchone()
        if product is None:
            return jsonify({"error": "商品が見つかりません"}), 404

        rows = con.execute(
            """SELECT id, name, comment, created_at
            FROM product_comments WHERE product_id=? ORDER BY id DESC""",
            (product_id,)
        ).fetchall()

    return jsonify([dict(row) for row in rows])


@app.post("/api/products/<int:product_id>/comments")
def create_product_comment(product_id):
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "名前とコメントを入力してください"}), 400

    name = data.get("name")
    comment = data.get("comment")
    if not isinstance(name, str) or not name.strip():
        return jsonify({"error": "名前を入力してください"}), 400
    if not isinstance(comment, str) or not comment.strip():
        return jsonify({"error": "コメントを入力してください"}), 400

    name = name.strip()[:30]
    comment = comment.strip()[:300]
    created_at = datetime.now(timezone.utc).isoformat()

    with connect() as con:
        product = con.execute(
            "SELECT id FROM products WHERE id=?", (product_id,)
        ).fetchone()
        if product is None:
            return jsonify({"error": "商品が見つかりません"}), 404

        cur = con.execute(
            """INSERT INTO product_comments
            (product_id, name, comment, created_at) VALUES (?, ?, ?, ?)""",
            (product_id, name, comment, created_at)
        )
        row = con.execute(
            "SELECT id, name, comment, created_at FROM product_comments WHERE id=?",
            (cur.lastrowid,)
        ).fetchone()

    return jsonify(dict(row)), 201


@app.get("/api/orders")
def get_orders():
    buyer_name = request.args.get("buyer_name", "").strip()[:30]
    if not buyer_name:
        return jsonify({"error": "購入者名を入力してください"}), 400

    with connect() as con:
        rows = con.execute(
            """SELECT id, product_id, product_name, price, created_at
            FROM orders WHERE buyer_name=? ORDER BY id DESC""",
            (buyer_name,)
        ).fetchall()

    return jsonify([dict(row) for row in rows])


# 商品リアクションの追加・取り消し
@app.post("/api/products/<int:product_id>/reactions")
def toggle_product_reaction(product_id):
    data = request.get_json(silent=True) or {}
    reaction = data.get("reaction")

    if reaction not in REACTIONS:
        return jsonify({"error": "invalid reaction"}), 400

    with connect() as con:
        product = con.execute(
            "SELECT id FROM products WHERE id=?", (product_id,)
        ).fetchone()

        if product is None:
            return jsonify({"error": "not found"}), 404

        existing = con.execute(
            "SELECT id FROM product_reactions "
            "WHERE product_id=? AND reaction=? LIMIT 1",
            (product_id, reaction)
        ).fetchone()

        if existing:
            con.execute(
                "DELETE FROM product_reactions WHERE id=?",
                (existing["id"],)
            )
            action = "removed"
        else:
            con.execute(
                "INSERT INTO product_reactions(product_id,reaction) "
                "VALUES(?,?)",
                (product_id, reaction)
            )
            action = "added"

        counts = con.execute(
            "SELECT reaction, COUNT(*) AS count FROM product_reactions "
            "WHERE product_id=? GROUP BY reaction",
            (product_id,)
        ).fetchall()

    return jsonify({
        "action": action,
        "reactions": {r["reaction"]: r["count"] for r in counts}
    })


@app.post("/api/products/<int:product_id>/purchase")
def purchase_product(product_id):
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "購入者名を入力してください"}), 400

    buyer_name = data.get("buyer_name")

    if not isinstance(buyer_name, str) or not buyer_name.strip():
        return jsonify({"error": "購入者名を入力してください"}), 400

    buyer_name = buyer_name.strip()[:30]
    created_at = datetime.now(timezone.utc).isoformat()

    with connect() as con:
        cur = con.execute(
            """INSERT INTO orders
            (product_id, product_name, price, buyer_name, created_at)
            SELECT id, name, price, ?, ?
            FROM products
            WHERE id=? AND NOT EXISTS (
                SELECT 1 FROM orders WHERE product_id=products.id
            )""",
            (buyer_name, created_at, product_id)
        )

        if cur.rowcount == 0:
            product = con.execute(
                "SELECT id FROM products WHERE id=?", (product_id,)
            ).fetchone()
            if product is None:
                return jsonify({"error": "商品が見つかりません"}), 404
            return jsonify({"error": "この商品は売り切れです"}), 409

        order = con.execute(
            "SELECT * FROM orders WHERE id=?", (cur.lastrowid,)
        ).fetchone()

    return jsonify(dict(order)), 201


@app.delete("/api/products/<int:product_id>")
def cancel_product_listing(product_id):
    with connect() as con:
        con.execute("BEGIN IMMEDIATE")
        product = con.execute(
            "SELECT id FROM products WHERE id=?", (product_id,)
        ).fetchone()
        if product is None:
            return jsonify({"error": "商品が見つかりません"}), 404

        order = con.execute(
            "SELECT id FROM orders WHERE product_id=?", (product_id,)
        ).fetchone()
        if order is not None:
            return jsonify({"error": "購入済みの商品は取り消せません"}), 409

        con.execute(
            "DELETE FROM product_reactions WHERE product_id=?", (product_id,)
        )
        con.execute(
            "DELETE FROM product_comments WHERE product_id=?", (product_id,)
        )
        con.execute("DELETE FROM products WHERE id=?", (product_id,))

    return "", 204


# 商品を出品
@app.post("/api/products")
def create_product():
    name = request.form.get("name", "").strip()[:100]
    description = request.form.get("description", "").strip()[:1000]
    price_text = request.form.get("price", "").strip()
    image = request.files.get("image")

    if not name or not description or not price_text or not image:
        return jsonify({"error": "すべての項目を入力してください"}), 400

    try:
        price = int(price_text)
        if price < 0:
            raise ValueError
    except ValueError:
        return jsonify({"error": "価格は0以上の整数で入力してください"}), 400

    filename = secure_filename(image.filename or "")
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if extension not in ALLOWED_EXTENSIONS:
        return jsonify({"error": "対応していない画像形式です"}), 400

    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

    saved_name = f"{uuid4().hex}.{extension}"
    image_path = UPLOAD_FOLDER / saved_name
    image.save(image_path)

    image_url = f"/static/uploads/{saved_name}"
    created_at = datetime.now(timezone.utc).isoformat()

    with connect() as con:
        cur = con.execute(
            """INSERT INTO products
            (name, price, description, image, created_at)
            VALUES (?, ?, ?, ?, ?)""",
            (name, price, description, image_url, created_at)
        )

        row = con.execute(
            "SELECT * FROM products WHERE id=?",
            (cur.lastrowid,)
        ).fetchone()

    return jsonify(dict(row)), 201



if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=False)
