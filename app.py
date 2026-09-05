from functools import wraps
import os
import sqlite3

from flask import Flask, jsonify, render_template, request, redirect, url_for, session
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")

DATABASE = os.environ.get("DATABASE_PATH", os.path.join(app.root_path, "database.db"))


# ---------------- DATABASE CONNECTION ----------------
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ---------------- CREATE TABLES ----------------
def create_tables():
    conn = get_db_connection()

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            price REAL NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT NOT NULL DEFAULT ''
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL CHECK (quantity > 0),
            total REAL NOT NULL CHECK (total >= 0),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)

    conn.commit()
    conn.close()


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            if request.path.startswith("/api/"):
                return jsonify(error="Authentication required"), 401
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped_view


def payload(required=()):
    values = request.get_json(silent=True) or request.form
    data = {key: str(values.get(key, "")).strip() for key in values.keys()}
    missing = [key for key in required if not data.get(key)]
    if missing:
        raise ValueError("Missing required fields: " + ", ".join(missing))
    return data


def product_values(data, partial=False):
    values = {}
    if not partial or "name" in data:
        if not data.get("name", "").strip():
            raise ValueError("Product name is required")
        values["name"] = data["name"].strip()
    if not partial or "category" in data:
        values["category"] = data.get("category", "").strip()
    if not partial or "price" in data:
        try:
            values["price"] = float(data.get("price", ""))
            if values["price"] < 0:
                raise ValueError
        except (TypeError, ValueError):
            raise ValueError("Price must be a non-negative number")
    if not partial or "quantity" in data:
        try:
            values["quantity"] = int(data.get("quantity", ""))
            if values["quantity"] < 0:
                raise ValueError
        except (TypeError, ValueError):
            raise ValueError("Quantity must be a non-negative integer")
    return values


def as_dict(row):
    return dict(row) if row else None


# ---------------- HOME ----------------
@app.route("/")
def index():
    return redirect(url_for("dashboard" if "user_id" in session else "login"))


# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":
        try:
            data = payload(("username", "password"))
            if len(data["password"]) < 6:
                raise ValueError("Password must contain at least 6 characters")
            conn = get_db_connection()
            conn.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (data["username"], generate_password_hash(data["password"]))
            )
            conn.commit()
            conn.close()
            return (jsonify(message="User registered"), 201) if request.is_json else redirect(url_for("login"))
        except (ValueError, sqlite3.IntegrityError) as error:
            if request.is_json:
                return jsonify(error=str(error)), 400
            return render_template("register.html", error="Username is already in use or input is invalid.")

    return render_template("register.html")


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        data = payload(("username", "password"))
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (data["username"],)).fetchone()
        conn.close()
        password_matches = False
        if user:
            if user["password"].startswith(("scrypt:", "pbkdf2:", "argon2:")):
                password_matches = check_password_hash(user["password"], data["password"])
            else:
                password_matches = user["password"] == data["password"]
            if password_matches and not user["password"].startswith(("scrypt:", "pbkdf2:", "argon2:")):
                conn = get_db_connection()
                conn.execute("UPDATE users SET password = ? WHERE id = ?", (generate_password_hash(data["password"]), user["id"]))
                conn.commit()
                conn.close()
        if user and password_matches:
            session.clear()
            session.update(user_id=user["id"], username=user["username"])
            return (jsonify(user={"id": user["id"], "username": user["username"]}) if request.is_json else redirect(url_for("dashboard")))
        return (jsonify(error="Invalid username or password"), 401) if request.is_json else render_template("login.html", error="Invalid username or password")

    return render_template("login.html")


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    product_count = conn.execute(
        "SELECT COUNT(*) FROM products"
    ).fetchone()[0]

    total_stock = conn.execute(
        "SELECT COALESCE(SUM(quantity), 0) FROM products"
    ).fetchone()[0]

    supplier_count = conn.execute(
        "SELECT COUNT(*) FROM suppliers"
    ).fetchone()[0]

    sales_count = conn.execute(
        "SELECT COUNT(*) FROM sales"
    ).fetchone()[0]

    conn.close()

    return render_template(
        "dashboard.html",
        product_count=product_count,
        total_stock=total_stock,
        supplier_count=supplier_count,
        sales_count=sales_count
    )


# ---------------- PRODUCTS ----------------
@app.route("/products")
@login_required
def products():

    conn = get_db_connection()

    products = conn.execute(
        "SELECT * FROM products"
    ).fetchall()

    conn.close()

    return render_template("products.html", products=products)


# ---------------- ADD PRODUCT ----------------
@app.route("/add_product", methods=["GET", "POST"])
@login_required
def add_product():

    if request.method == "POST":

        name = request.form["name"]
        category = request.form["category"]
        price = request.form["price"]
        quantity = request.form["quantity"]

        conn = get_db_connection()

        conn.execute("""
            INSERT INTO products
            (name, category, price, quantity)
            VALUES (?, ?, ?, ?)
        """, (name, category, price, quantity))

        conn.commit()
        conn.close()

        return redirect(url_for("products"))

    return render_template("product_form.html")


# ---------------- DELETE PRODUCT ----------------
@app.route("/delete_product/<int:id>")
@login_required
def delete_product(id):

    conn = get_db_connection()

    conn.execute(
        "DELETE FROM products WHERE id = ?",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("products"))


# ---------------- SUPPLIERS ----------------
@app.route("/suppliers")
@login_required
def suppliers():

    conn = get_db_connection()

    suppliers = conn.execute(
        "SELECT * FROM suppliers"
    ).fetchall()

    conn.close()

    return render_template("suppliers.html", suppliers=suppliers)


# ---------------- ADD SUPPLIER ----------------
@app.route("/add_supplier", methods=["GET", "POST"])
@login_required
def add_supplier():

    if request.method == "POST":

        name = request.form["name"]
        phone = request.form["phone"]
        email = request.form["email"]

        conn = get_db_connection()

        conn.execute("""
            INSERT INTO suppliers
            (name, phone, email)
            VALUES (?, ?, ?)
        """, (name, phone, email))

        conn.commit()
        conn.close()

        return redirect(url_for("suppliers"))

    return render_template("supplier_form.html")


# ---------------- SALES ----------------
@app.route("/sales")
@login_required
def sales():

    conn = get_db_connection()

    sales = conn.execute("""
        SELECT sales.id, products.name,
               sales.quantity, sales.total
        FROM sales
        JOIN products ON sales.product_id = products.id
    """).fetchall()

    conn.close()

    return render_template("sales.html", sales=sales)


@app.route("/api/products", methods=["GET", "POST"])
@login_required
def products_api():
    conn = get_db_connection()
    if request.method == "GET":
        rows = conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
        conn.close()
        return jsonify(products=[as_dict(row) for row in rows])
    try:
        data = payload(("name", "price", "quantity"))
        values = product_values(data)
        cursor = conn.execute("INSERT INTO products (name, category, price, quantity) VALUES (?, ?, ?, ?)", tuple(values.values()))
        conn.commit()
        row = conn.execute("SELECT * FROM products WHERE id = ?", (cursor.lastrowid,)).fetchone()
        conn.close()
        return jsonify(product=as_dict(row)), 201
    except ValueError as error:
        conn.close()
        return jsonify(error=str(error)), 400


@app.route("/api/products/<int:product_id>", methods=["GET", "PUT", "PATCH", "DELETE"])
@login_required
def product_api(product_id):
    conn = get_db_connection()
    product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if not product:
        conn.close()
        return jsonify(error="Product not found"), 404
    if request.method == "GET":
        conn.close()
        return jsonify(product=as_dict(product))
    if request.method == "DELETE":
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
        conn.close()
        return jsonify(message="Product deleted")
    try:
        values = product_values(payload(), partial=True)
        if not values:
            raise ValueError("At least one product field is required")
        assignments = ", ".join(f"{key} = ?" for key in values)
        conn.execute(f"UPDATE products SET {assignments} WHERE id = ?", (*values.values(), product_id))
        conn.commit()
        updated = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        conn.close()
        return jsonify(product=as_dict(updated))
    except ValueError as error:
        conn.close()
        return jsonify(error=str(error)), 400


@app.route("/api/suppliers", methods=["GET", "POST"])
@login_required
def suppliers_api():
    conn = get_db_connection()
    if request.method == "GET":
        rows = conn.execute("SELECT * FROM suppliers ORDER BY id DESC").fetchall()
        conn.close()
        return jsonify(suppliers=[as_dict(row) for row in rows])
    try:
        data = payload(("name",))
        cursor = conn.execute("INSERT INTO suppliers (name, phone, email) VALUES (?, ?, ?)", (data["name"], data.get("phone", ""), data.get("email", "")))
        conn.commit()
        row = conn.execute("SELECT * FROM suppliers WHERE id = ?", (cursor.lastrowid,)).fetchone()
        conn.close()
        return jsonify(supplier=as_dict(row)), 201
    except ValueError as error:
        conn.close()
        return jsonify(error=str(error)), 400


@app.route("/api/sales", methods=["GET", "POST"])
@login_required
def sales_api():
    conn = get_db_connection()
    if request.method == "GET":
        rows = conn.execute("SELECT sales.*, products.name AS product_name FROM sales JOIN products ON products.id = sales.product_id ORDER BY sales.id DESC").fetchall()
        conn.close()
        return jsonify(sales=[as_dict(row) for row in rows])
    try:
        data = payload(("product_id", "quantity"))
        product_id, quantity = int(data["product_id"]), int(data["quantity"])
        product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if not product or quantity <= 0 or quantity > product["quantity"]:
            raise ValueError
        total = round(product["price"] * quantity, 2)
        conn.execute("UPDATE products SET quantity = quantity - ? WHERE id = ?", (quantity, product_id))
        cursor = conn.execute("INSERT INTO sales (product_id, quantity, total) VALUES (?, ?, ?)", (product_id, quantity, total))
        conn.commit()
        sale = conn.execute("SELECT sales.*, products.name AS product_name FROM sales JOIN products ON products.id = sales.product_id WHERE sales.id = ?", (cursor.lastrowid,)).fetchone()
        conn.close()
        return jsonify(sale=as_dict(sale)), 201
    except (ValueError, TypeError):
        conn.rollback()
        conn.close()
        return jsonify(error="Invalid product or quantity"), 400


@app.route("/api/dashboard")
@login_required
def dashboard_api():
    conn = get_db_connection()
    data = {
        "products": conn.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        "stock": conn.execute("SELECT COALESCE(SUM(quantity), 0) FROM products").fetchone()[0],
        "suppliers": conn.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0],
        "sales": conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0],
    }
    conn.close()
    return jsonify(data)


# ---------------- LOGOUT ----------------
@app.route("/logout", methods=["GET", "POST"])
def logout():

    session.clear()

    return jsonify(message="Logged out") if request.is_json else redirect(url_for("login"))


create_tables()


# ---------------- RUN APPLICATION ----------------
if __name__ == "__main__":
    create_tables()
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1")