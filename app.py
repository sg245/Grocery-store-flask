from flask import Flask, render_template, request, redirect, flash ,session
from db import get_db_connection
import hashlib 

app = Flask(__name__)
app.secret_key = "secret123"

@app.route("/")
def home():

    search_query = request.args.get("search")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if search_query:
        cursor.execute(
            "SELECT * FROM products WHERE name LIKE %s",
            (f"%{search_query}%",)
        )
    else:
        category = request.args.get("category")

        if category:
            cursor.execute(
                "SELECT * FROM products WHERE category = %s",
                (category,)
            )
        else:
            cursor.execute("SELECT * FROM products")
            products = cursor.fetchall()
            wishlist_ids = []

            if "user_id" in session:
                cursor.execute(
                    "SELECT product_id FROM wishlist WHERE user_id=%s",
                    (session["user_id"],)
                )
                wishlist_ids = [row["product_id"] for row in cursor.fetchall()]

    cursor.close()
    conn.close()

    user_name = session.get("user_name")

    cart_count = 0
    if "user_id" in session:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT SUM(quantity) FROM cart WHERE user_id = %s",
            (session["user_id"],)
        )
        result = cursor.fetchone()
        cart_count = result[0] if result[0] else 0
        cursor.close()
        conn.close()

    return render_template(
        "home.html",
        user_name=user_name,
        products=products,
        cart_count=cart_count,
        wishlist_ids=wishlist_ids
    )




# Signup route
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        # ✅ must match HTML input name=""
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

        print(name, email, password)  # debugging

        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
                (name, email, hashed_password)
            )
            conn.commit()
            flash("User registered successfully!", "success")
            return redirect("/")

        except Exception as e:
            conn.rollback()
            flash("Error: " + str(e), "danger")
            return redirect("/register")

        finally:
            cursor.close()
            conn.close()

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":

        # 1️⃣ Get form data
        email = request.form.get("email")
        password = request.form.get("password")

        # 2️⃣ Hash the entered password
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        # 3️⃣ Connect to database
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 4️⃣ Fetch user with this email
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()  # returns dict or None

        cursor.close()
        conn.close()

        # 5️⃣ Check if user exists and password matches
        if user and user["password"] == hashed_password:
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            flash("Login successful!", "success")
            return redirect("/")  # redirect to home or dashboard
        else:
            flash("Invalid email or password", "danger")
            return redirect("/login")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()  # remove all session data
    flash("You have been logged out.", "success")
    return redirect("/")

@app.route("/add-to-cart/<int:product_id>")
def add_to_cart(product_id):

    if "user_id" not in session:
        flash("Please login first", "warning")
        return redirect("/login")

    user_id = session["user_id"]

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # check if product already in cart
    cursor.execute(
        "SELECT * FROM cart WHERE user_id=%s AND product_id=%s",
        (user_id, product_id)
    )
    item = cursor.fetchone()

    if item:
        cursor.execute(
            "UPDATE cart SET quantity = quantity + 1 WHERE id=%s",
            (item["id"],)
        )
    else:
        cursor.execute(
            "INSERT INTO cart (user_id, product_id, quantity) VALUES (%s, %s, 1)",
            (user_id, product_id)
        )

    conn.commit()
    cursor.close()
    conn.close()

    flash("Added to cart", "success")
    return redirect("/")

@app.route("/cart")
def cart():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
                SELECT 
                products.id AS product_id,
                products.name,
                products.price,
                cart.quantity
            FROM cart
            JOIN products ON cart.product_id = products.id
            WHERE cart.user_id = %s
        """,
    (session["user_id"],))


    cart_items = cursor.fetchall()

    total = 0
    for item in cart_items:
        total += item["price"] * item["quantity"]

    cursor.close()
    conn.close()

    return render_template(
        "cart.html",
        cart_items=cart_items,
        total=total
    )

@app.route("/remove-from-cart/<int:product_id>")
def remove_from_cart(product_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM cart WHERE product_id = %s AND user_id = %s",
        (product_id, session["user_id"])
    )

    conn.commit()
    cursor.close()
    conn.close()

    return redirect("/cart")

@app.route("/increase/<int:product_id>")
def increase_quantity(product_id):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE cart SET quantity = quantity + 1 WHERE product_id = %s AND user_id = %s",
        (product_id, session["user_id"])
    )

    conn.commit()
    cursor.close()
    conn.close()

    return redirect("/cart")

@app.route("/decrease/<int:product_id>")
def decrease_quantity(product_id):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE cart SET quantity = quantity - 1 WHERE product_id = %s AND user_id = %s AND quantity > 1",
        (product_id, session["user_id"])
    )

    conn.commit()
    cursor.close()
    conn.close()

    return redirect("/cart")

@app.route("/checkout")
def checkout():

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT products.name, products.price, cart.quantity
        FROM cart
        JOIN products ON cart.product_id = products.id
        WHERE cart.user_id = %s
    """, (user_id,))

    cart_items = cursor.fetchall()

    total = 0
    for item in cart_items:
        total += item["price"] * item["quantity"]

    cursor.close()
    conn.close()

    return render_template(
        "checkout.html",
        cart_items=cart_items,
        total=total
    )

@app.route("/confirm-order", methods=["POST"])
def confirm_order():
    payment_method = request.form.get("payment")

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT products.name, products.price, cart.quantity
        FROM cart
        JOIN products ON cart.product_id = products.id
        WHERE cart.user_id = %s
    """, (user_id,))

    cart_items = cursor.fetchall()

    total = sum(item["price"] * item["quantity"] for item in cart_items)

    cursor.execute(
    "INSERT INTO orders (user_id, total_amount, payment_method) VALUES (%s, %s, %s)",
    (user_id, total, payment_method)
)




    order_id = cursor.lastrowid

    for item in cart_items:
        cursor.execute(
            """
            INSERT INTO order_items
            (order_id, product_name, price, quantity)
            VALUES (%s, %s, %s, %s)
            """,
            (order_id, item["name"], item["price"], item["quantity"])
        )

    cursor.execute("DELETE FROM cart WHERE user_id = %s", (user_id,))

    conn.commit()
    cursor.close()
    conn.close()

    return render_template("order_success.html", order_id=order_id)


@app.route("/orders")
def user_orders():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    orders = []   # ✅ IMPORTANT — define first

    cursor.execute("""
        SELECT id, total_amount, status, created_at
        FROM orders
        WHERE user_id = %s
        ORDER BY id DESC
    """, (session["user_id"],))


    orders = cursor.fetchall()
    print("ORDERS FROM DB:", orders)


    cursor.close()
    conn.close()

    return render_template("orders.html", orders=orders)


@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True, buffered=True)

        cur.execute(
            "SELECT * FROM admin WHERE username=%s AND password=%s",
            (username, password)
        )
        admin = cur.fetchone()
        cur.close()
        conn.close()

        if admin:
            session["admin"] = username
            return redirect("/admin/dashboard")
        else:
            return "Invalid admin login"

    return render_template("admin_login.html")

import os
from werkzeug.utils import secure_filename

IMAGES_FOLDER = "static/images"
app.config["IMAGES_FOLDER"] = IMAGES_FOLDER

@app.route("/admin/dashboard")
def admin_dashboard():

    if "admin" not in session:
        return redirect("/admin")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # total users
    cursor.execute("SELECT COUNT(*) AS total_users FROM users")
    total_users = cursor.fetchone()["total_users"]

    # total orders
    cursor.execute("SELECT COUNT(*) AS total_orders FROM orders")
    total_orders = cursor.fetchone()["total_orders"]

    # total revenue
    cursor.execute("SELECT IFNULL(SUM(total_amount), 0) AS revenue FROM orders")
    total_revenue = cursor.fetchone()["revenue"]

    # total products
    cursor.execute("SELECT COUNT(*) AS total_products FROM products")
    total_products = cursor.fetchone()["total_products"]

    cursor.close()
    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_orders=total_orders,
        total_revenue=total_revenue,
        total_products=total_products
    )


@app.route("/admin/orders")
def admin_orders():

    if "admin" not in session:
        return redirect("/admin")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # fetch all orders
    cursor.execute("""
        SELECT 
            orders.id,
            orders.total_amount,
            orders.created_at,
            users.name AS customer_name
        FROM orders
        JOIN users ON orders.user_id = users.id
        ORDER BY orders.id DESC
    """)

    orders = cursor.fetchall()

    # fetch items for each order
    for order in orders:
        cursor.execute(
            "SELECT product_name, quantity, price FROM order_items WHERE order_id=%s",
            (order["id"],)
        )
        order["items"] = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("admin_orders.html", orders=orders)

@app.route("/admin/update-order-status", methods=["POST"])
def update_order_status():

    if "admin" not in session:
        return redirect("/admin")

    order_id = request.form.get("order_id")
    status = request.form.get("status")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE orders SET status=%s WHERE id=%s",
        (status, order_id)
    )

    conn.commit()
    cursor.close()
    conn.close()

    return redirect("/admin/orders")


@app.route("/admin/add-product", methods=["GET", "POST"])
def admin_add_product():

    if "admin" not in session:
        return redirect("/admin")

    if request.method == "POST":
        name = request.form["name"]
        price = request.form["price"]
        image = request.files["image"]

        filename = secure_filename(image.filename)
        image_path = os.path.join(app.config["IMAGES_FOLDER"], filename)

        image.save(image_path)

        conn = get_db_connection()
        cursor = conn.cursor()

        category = request.form["category"]

        cursor.execute(
            "INSERT INTO products (name, price, image_url, category) VALUES (%s, %s, %s, %s)",
            (name, price, f"images/{filename}", category)
        )


        conn.commit()
        cursor.close()
        conn.close()

        return redirect("/admin/products")

    return render_template("admin_add_product.html")

@app.route("/admin/products")
def admin_products():

    if "admin" not in session:
        return redirect("/admin")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("admin_products.html", products=products)

@app.route("/admin/delete/<int:id>")
def delete_product(id):

    if "admin" not in session:
        return redirect("/admin")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM products WHERE id=%s", (id,))
    conn.commit()

    cursor.close()
    conn.close()

    return redirect("/admin/products")

@app.route("/product/<int:product_id>")
def product_detail(product_id):

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM products WHERE id = %s",
        (product_id,)
    )

    product = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template("product_detail.html", product=product)

@app.route("/product/<int:id>")
def product_details(id):

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM products WHERE id = %s", (id,))
    product = cursor.fetchone()

    cursor.close()
    conn.close()

    if not product:
        return "Product not found"

    return render_template(
        "product_details.html",
        product=product
    )
@app.route("/add-to-wishlist/<int:product_id>")
def add_to_wishlist(product_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT IGNORE INTO wishlist (user_id, product_id)
        VALUES (%s, %s)
    """, (session["user_id"], product_id))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(request.referrer or "/")

@app.route("/remove-from-wishlist/<int:product_id>")
def remove_from_wishlist(product_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM wishlist
        WHERE user_id=%s AND product_id=%s
    """, (session["user_id"], product_id))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect("/wishlist")

@app.route("/wishlist")
def wishlist():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT products.*
        FROM wishlist
        JOIN products ON wishlist.product_id = products.id
        WHERE wishlist.user_id = %s
    """, (session["user_id"],))

    wishlist_items = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("wishlist.html", wishlist_items=wishlist_items)


@app.route("/toggle-wishlist/<int:product_id>")
def toggle_wishlist(product_id):

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # check if already in wishlist
    cursor.execute(
        "SELECT * FROM wishlist WHERE user_id=%s AND product_id=%s",
        (user_id, product_id)
    )
    item = cursor.fetchone()

    if item:
        # remove
        cursor.execute(
            "DELETE FROM wishlist WHERE user_id=%s AND product_id=%s",
            (user_id, product_id)
        )
    else:
        # add
        cursor.execute(
            "INSERT INTO wishlist (user_id, product_id) VALUES (%s, %s)",
            (user_id, product_id)
        )

    conn.commit()
    cursor.close()
    conn.close()

    return redirect("/")

@app.route("/payment")
def payment():

    if "user_id" not in session:
        return redirect("/login")

    return render_template("payment.html")


if __name__ == "__main__":
    app.run(debug=True)