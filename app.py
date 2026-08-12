from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3

app = Flask(__name__)
app.secret_key = "inventory_secret_key"

DATABASE = "database.db"


# ---------------- DATABASE CONNECTION ----------------
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------- CREATE TABLES ----------------
def create_tables():
    conn = get_db_connection()

    conn.execute("""
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
            quantity INTEGER NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            quantity INTEGER,
            total REAL
        )
    """)

    conn.commit()
    conn.close()


# ---------------- HOME ----------------
@app.route("/")
def index():
    return render_template("index.html")


# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()

        try:
            conn.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, password)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return "Username already exists"

        conn.close()

        return redirect(url_for("login"))

    return render_template("register.html")


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()

        user = conn.execute(
            "SELECT * FROM users WHERE username = ? AND password = ?",
            (username, password)
        ).fetchone()

        conn.close()

        if user:
            session["username"] = username
            return redirect(url_for("dashboard"))

        return "Invalid username or password"

    return render_template("login.html")


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():

    if "username" not in session:
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
def products():

    if "username" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    products = conn.execute(
        "SELECT * FROM products"
    ).fetchall()

    conn.close()

    return render_template("products.html", products=products)


# ---------------- ADD PRODUCT ----------------
@app.route("/add_product", methods=["GET", "POST"])
def add_product():

    if "username" not in session:
        return redirect(url_for("login"))

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

    return render_template("add_product.html")


# ---------------- DELETE PRODUCT ----------------
@app.route("/delete_product/<int:id>")
def delete_product(id):

    if "username" not in session:
        return redirect(url_for("login"))

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
def suppliers():

    if "username" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    suppliers = conn.execute(
        "SELECT * FROM suppliers"
    ).fetchall()

    conn.close()

    return render_template("suppliers.html", suppliers=suppliers)


# ---------------- ADD SUPPLIER ----------------
@app.route("/add_supplier", methods=["GET", "POST"])
def add_supplier():

    if "username" not in session:
        return redirect(url_for("login"))

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

    return render_template("add_supplier.html")


# ---------------- SALES ----------------
@app.route("/sales")
def sales():

    if "username" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    sales = conn.execute("""
        SELECT sales.id, products.name,
               sales.quantity, sales.total
        FROM sales
        JOIN products ON sales.product_id = products.id
    """).fetchall()

    conn.close()

    return render_template("sales.html", sales=sales)


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# ---------------- RUN APPLICATION ----------------
if __name__ == "__main__":
    create_tables()
    app.run(debug=True)