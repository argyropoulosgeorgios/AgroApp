from flask import Flask, render_template, request, redirect, session, url_for, send_file
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import csv
import io

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Αντιστοίχιση χρώματος σε κατηγορίες
def category_color(category):
    mapping = {
        "Λίπασμα": "bg-success",
        "Καύσιμα": "bg-danger",
        "Ημερομίσθια": "bg-primary",
        "Αναλώσιμα": "bg-warning text-dark",
        "Άλλα": "bg-secondary"
    }
    return mapping.get(category, "bg-light text-dark")

# Αρχικοποίηση ΒΔ αν δεν υπάρχει
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            birthdate TEXT,
            email TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date TEXT,
            category TEXT,
            amount REAL,
            note TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date TEXT,
            customer TEXT,
            amount REAL,
            description TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date TEXT,
            item TEXT,
            quantity INTEGER,
            notes TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')


    users = [
        ("user1", "1234", "User One", "1990-01-01", "user1@example.com"),
        ("danai", "danaisagapw97", "Danai", "1995-02-14", "danai@example.com"),
        ("admin", "1234", "Admin", "1980-01-01", "admin@example.com")
    ]
    for username, pw, full_name, birthdate, email in users:
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        if not c.fetchone():
            pw_hash = generate_password_hash(pw)
            c.execute("INSERT INTO users (username, password_hash, full_name, birthdate, email) VALUES (?, ?, ?, ?, ?)",
                      (username, pw_hash, full_name, birthdate, email))

    conn.commit()
    conn.close()

@app.context_processor
def utility_processor():
    return dict(category_color=category_color)

@app.route('/admin')
def admin_panel():
    if 'username' not in session or session['username'] != 'admin':
        return redirect('/')
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT id, username, full_name, birthdate, email FROM users")
    users = c.fetchall()
    c.execute("SELECT expenses.id, expenses.date, expenses.category, expenses.amount, expenses.note, users.username FROM expenses JOIN users ON expenses.user_id = users.id ORDER BY expenses.date DESC")
    expenses = c.fetchall()
    c.execute("SELECT users.username, SUM(expenses.amount) FROM expenses JOIN users ON expenses.user_id = users.id GROUP BY users.username")
    totals = c.fetchall()
    c.execute("SELECT invoices.id, invoices.date, invoices.customer, invoices.amount, invoices.description, users.username FROM invoices JOIN users ON invoices.user_id = users.id ORDER BY invoices.date DESC")
    invoices = c.fetchall()
    conn.close()
    return render_template('admin.html', users=users, expenses=expenses, totals=totals, invoices=invoices)

@app.route('/admin/create_user', methods=['GET', 'POST'])
def admin_create_user():
    if 'username' not in session or session['username'] != 'admin':
        return redirect('/')
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        full_name = request.form['full_name']
        birthdate = request.form['birthdate']
        email = request.form['email']
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        password_hash = generate_password_hash(password)
        c.execute("INSERT INTO users (username, password_hash, full_name, birthdate, email) VALUES (?, ?, ?, ?, ?)",
                  (username, password_hash, full_name, birthdate, email))
        conn.commit()
        conn.close()
        return redirect('/admin')
    return render_template('create_user.html')

@app.route('/admin/export')
def admin_export():
    if 'username' not in session or session['username'] != 'admin':
        return redirect('/')
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT expenses.date, expenses.category, expenses.amount, expenses.note, users.username FROM expenses JOIN users ON expenses.user_id = users.id")
    data = c.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Ημερομηνία', 'Κατηγορία', 'Ποσό', 'Σχόλιο', 'Χρήστης'])
    for row in data:
        writer.writerow(row)

    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode()), mimetype='text/csv', as_attachment=True, download_name='expenses.csv')


@app.route('/expenses', methods=['GET', 'POST'])
def expenses():
    if 'user_id' not in session:
        return redirect('/login')
    user_id = session['user_id']
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    if request.method == 'POST':
        date = request.form['date']
        category = request.form['category']
        amount = float(request.form['amount'])
        note = request.form['note']
        c.execute("INSERT INTO expenses (user_id, date, category, amount, note) VALUES (?, ?, ?, ?, ?)",
                  (user_id, date, category, amount, note))
        conn.commit()
        return redirect('/expenses')

    c.execute("SELECT * FROM expenses WHERE user_id = ? ORDER BY date DESC", (user_id,))
    expenses = c.fetchall()
    conn.close()

    # Σωστό indexing
    expenses = [
        (r[0], r[2], r[3], float(r[4]), r[5])
        for r in expenses
    ]

    return render_template('expenses.html', expenses=expenses)



@app.route('/production', methods=['GET', 'POST'])
def production():
    if 'user_id' not in session:
        return redirect('/login')
    user_id = session['user_id']
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    if request.method == 'POST':
        date = request.form['date']
        product = request.form['product']
        quantity = request.form['quantity']
        notes = request.form['notes']
        c.execute(
            "INSERT INTO production (user_id, date, product, quantity, notes) VALUES (?, ?, ?, ?, ?)",
            (user_id, date, product, quantity, notes)
        )
        conn.commit()
        return redirect('/production')

    c.execute("SELECT * FROM production WHERE user_id = ? ORDER BY date DESC", (user_id,))
    production_records = c.fetchall()
    conn.close()
    return render_template('production.html', production=production_records)



@app.route('/admin/delete_expense/<int:id>', methods=['POST'])
def admin_delete_expense(id):
    if 'username' not in session or session['username'] != 'admin':
        return redirect('/')
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("DELETE FROM expenses WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect('/admin')

@app.route('/invoices', methods=['GET', 'POST'])
def invoices():
    if 'user_id' not in session:
        return redirect('/login')
    user_id = session['user_id']
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    if request.method == 'POST':
        date = request.form['date']
        customer = request.form['customer']
        amount = request.form['amount']
        description = request.form['description']
        c.execute("INSERT INTO invoices (user_id, date, customer, amount, description) VALUES (?, ?, ?, ?, ?)",
                  (user_id, date, customer, amount, description))
        conn.commit()
        return redirect('/invoices')

    c.execute("SELECT * FROM invoices WHERE user_id = ? ORDER BY date DESC", (user_id,))
    invoices = c.fetchall()
    conn.close()
    return render_template('invoices.html', invoices=invoices)

@app.route('/invoices/delete/<int:id>', methods=['POST'])
def delete_invoice(id):
    if 'user_id' not in session:
        return redirect('/login')
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("DELETE FROM invoices WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect('/invoices')

@app.route('/invoices/export')
def export_invoices():
    if 'user_id' not in session:
        return redirect('/login')
    user_id = session['user_id']
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT date, customer, amount, description FROM invoices WHERE user_id = ?", (user_id,))
    data = c.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Ημερομηνία', 'Πελάτης', 'Ποσό', 'Περιγραφή'])
    for row in data:
        writer.writerow(row)

    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode()), mimetype='text/csv', as_attachment=True, download_name='invoices.csv')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()
        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            return redirect('/')
        else:
            return "Λάθος στοιχεία"
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/expenses/export')
def export_expenses():
    if 'user_id' not in session:
        return redirect('/login')
    user_id = session['user_id']
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT date, category, amount, note FROM expenses WHERE user_id = ?", (user_id,))
    data = c.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Ημερομηνία', 'Κατηγορία', 'Ποσό', 'Σχόλιο'])
    for row in data:
        writer.writerow(row)

    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode()), mimetype='text/csv', as_attachment=True, download_name='expenses.csv')


@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,))
    total_expenses = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM invoices WHERE user_id = ?", (user_id,))
    total_invoices = c.fetchone()[0]
    conn.close()

    return render_template('index.html', total_expenses=total_expenses, total_invoices=total_invoices)


@app.route('/delete/<int:id>', methods=['POST'])
def delete_expense(id):
    if 'user_id' not in session:
        return redirect('/login')
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("DELETE FROM expenses WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/inventory', methods=['GET', 'POST'])
def inventory():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # Get filters from form
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    category = request.args.get('category')
    product = request.args.get('product')
    search = request.args.get('search')

    query = "SELECT * FROM inventory WHERE user_id = ?"
    params = [user_id]

    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
    if category and category != 'Όλα':
        query += " AND category = ?"
        params.append(category)
    if product and product != 'Όλα':
        query += " AND product = ?"
        params.append(product)
    if search:
        query += " AND (product LIKE ? OR notes LIKE ?)"
        params.append(f"%{search}%")
        params.append(f"%{search}%")

    query += " ORDER BY date DESC"

    c.execute(query, tuple(params))
    inventory_data = c.fetchall()

    # Φόρτωση προϊόντων από το catalog για το dropdown
    c.execute("SELECT name, category FROM products_catalog ORDER BY name")
    catalog = c.fetchall()

    # Για τα dropdown φίλτρα
    c.execute("SELECT DISTINCT category FROM inventory WHERE user_id = ?", (user_id,))
    categories = [row[0] for row in c.fetchall()]
    c.execute("SELECT DISTINCT product FROM inventory WHERE user_id = ?", (user_id,))
    products = [row[0] for row in c.fetchall()]

    conn.close()

    return render_template('inventory.html', inventory_data=inventory_data, products_catalog=catalog, categories=categories, products=products)




@app.route('/inventory/delete/<int:id>', methods=['POST'])
def delete_inventory_item(id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("DELETE FROM inventory WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect('/inventory')

@app.route('/account_settings', methods=['GET', 'POST'])
def account_settings():
    if 'user_id' not in session:
        return redirect('/login')
    user_id = session['user_id']
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    if request.method == 'POST':
        new_email = request.form['email']
        new_password = request.form.get('password')
        if new_password:
            password_hash = generate_password_hash(new_password)
            c.execute("UPDATE users SET email = ?, password_hash = ? WHERE id = ?", (new_email, password_hash, user_id))
        else:
            c.execute("UPDATE users SET email = ? WHERE id = ?", (new_email, user_id))
        conn.commit()
        conn.close()
        return redirect(url_for('account_settings'))
    else:
        c.execute("SELECT email FROM users WHERE id = ?", (user_id,))
        email = c.fetchone()[0]
        conn.close()
        return render_template('account_settings.html', email=email)


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if 'user_id' not in session:
        return redirect('/login')
    if request.method == 'POST':
        # Εδώ μπορείς να χειριστείς την αποστολή φόρμας επικοινωνίας (π.χ. αποστολή email)
        return render_template('contact.html', success=True)
    return render_template('contact.html', success=False)



@app.route('/inventory/export')
def export_inventory():
    if 'user_id' not in session:
        return redirect('/login')

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT name, quantity, unit, notes FROM inventory")
    data = c.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Όνομα', 'Ποσότητα', 'Μονάδα', 'Σχόλια'])
    for row in data:
        writer.writerow(row)

    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode()), mimetype='text/csv', as_attachment=True, download_name='inventory.csv')


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
