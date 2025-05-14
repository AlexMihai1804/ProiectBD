import os
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session, redirect, url_for
from db import Database

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change_this_in_prod")
database = Database()

STATUSES = ['pending', 'processing', 'shipped', 'completed', 'cancelled']

# --------------------------------------------------
#  FRONT‑END ROUTES
# --------------------------------------------------

@app.route('/')
def products_page():
    return render_template('products.html')

@app.route('/profile')
def profile():
    if 'user' not in session:
        return redirect(url_for('login'))
    cust = database.get_customer_by_username(session['user'])
    return render_template('profile.html', customer=cust)

@app.route('/orders')
def orders():
    if 'user' not in session:
        return redirect(url_for('login'))
    cid = database.get_customer_id(session['user'])
    raw = database.get_orders_by_customer(cid)
    for o in raw:
        o['qty'] = database.get_order_quantity(o['id_order'])
    return render_template('orders.html', orders=raw)

@app.route('/employees')
def employees():
    if 'employee' not in session:
        return redirect(url_for('employee_login'))
    dept = session.get('employee_dept')
    if dept == 'achizitii':
        return redirect(url_for('employees_achizitii'))
    if dept == 'sales':
        return redirect(url_for('employees_vanzari'))
    if dept == 'productie':
        return redirect(url_for('employees_productie'))
    return redirect(url_for('employee_login'))

@app.route('/employees/achizitii')
def employees_achizitii():
    if session.get('employee_dept') != 'achizitii':
        return redirect(url_for('employee_login'))
    return render_template('employees_achizitii.html')

@app.route('/employees/achizitii/orders')
def employees_achizitii_orders():
    if session.get('employee_dept') != 'achizitii':
        return redirect(url_for('employee_login'))
    return render_template('employees_achizitii_orders.html')

@app.route('/employees/achizitii/order/<int:order_id>')
def achizitii_order_detail(order_id: int):
    if session.get('employee_dept') != 'achizitii':
        return redirect(url_for('employee_login'))
    # basic ownership check
    eid = database.get_employee_id(session['employee'])

    # --- fix: fetch full row not scalar --------------------------------
    database.cursor.execute(
        "SELECT * FROM partner_orders WHERE id_order=%s AND id_employee=%s",
        (order_id, eid)
    )
    order = database.cursor.fetchone()          # dict row or None
    # -------------------------------------------------------------------

    if not order:
        return "Order not found or not assigned to you", 404
    items = database.get_partner_order_items(order_id)
    partner = database._fetchone_scalar(
        "SELECT name FROM partners WHERE id_partner=%s",
        (order['id_partner'],))
    order['date_fmt'] = order['data'].strftime('%Y-%m-%d %H:%M')
    return render_template('employees_achizitii_order.html',
                           order=order, items=items, partner=partner)

@app.route('/employees/vanzari')
def employees_vanzari():
    if session.get('employee_dept') != 'sales':
        return redirect(url_for('employee_login'))
    return render_template('employees_vanzari.html')

@app.route('/employees/vanzari/order/<int:order_id>', methods=['GET', 'POST'])
def employee_order_detail(order_id: int):
    # must be logged in as sales
    if session.get('employee_dept') != 'sales':
        return redirect(url_for('employee_login'))

    emp_user = session['employee']
    if request.method == 'POST':
        new_status = request.form.get('status')
        database.update_order_status(emp_user, order_id, new_status)

    # fetch order (ensure it belongs to current employee)
    emp_id = database.get_employee_id(emp_user)
    order = next(
        (o for o in database.get_orders_by_employee(emp_id) if o['id_order'] == order_id),
        None
    )
    if not order:
        return "Order not found or not assigned to you", 404

    items = database.get_order_items(order_id)
    order['qty'] = sum(i['quantity'] for i in items)

    # NEW – customer details
    customer = database.get_customer_by_id(order['id_client'])

    return render_template(
        'employees_vanzari_order.html',
        order=order,
        items=items,
        customer=customer,
        statuses=STATUSES
    )

@app.route('/employees/productie')
def employees_productie():
    if session.get('employee_dept') != 'productie':
        return redirect(url_for('employee_login'))
    return render_template('employees_productie.html')

# --------------------------------------------------
#  AUTH ROUTES (CUSTOMER & EMPLOYEE)
# --------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        # sanitize input --------------------------------------------------
        uname = request.form['username'].strip().lower()
        pwd   = request.form['password']
        # -----------------------------------------------------------------
        if database.verify_customer(uname, pwd):
            session.clear()
            session['user'] = uname
            # make 100 % sure no employee residue remains
            session.pop('employee',       None)
            session.pop('employee_dept',  None)
            return redirect(url_for('products_page'))
        error = 'Date invalide'
    return render_template('login.html', error=error)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    error = None
    if request.method == 'POST':
        data      = request.form
        # strip / lowercase username so the same user can later log in ----
        username  = data['username'].strip().lower()
        # -----------------------------------------------------------------
        res = database.create_customer(
            data['name'], data['surname'], username, data['password'],
            data['email'], data.get('address', ''), data.get('phone', '')
        )
        if res.get('success'):
            session.clear(); session['user'] = username
            return redirect(url_for('products_page'))
        error = res.get('error')
    return render_template('signup.html', error=error)

@app.route('/employee_login', methods=['GET', 'POST'])
def employee_login():
    error = None
    if request.method == 'POST':
        # sanitize --------------------------------------------------------
        uname = request.form['username'].strip().lower()
        pwd   = request.form['password']
        # -----------------------------------------------------------------
        if database.verify_employee(uname, pwd):
            session.clear()
            emp = database.get_employee_by_username(uname)
            session.update({'employee': uname, 'employee_dept': emp['department']})
            # ensure no customer data lingers
            session.pop('user', None)
            return redirect(url_for('employees'))
        error = 'Date invalide'
    return render_template('employee_login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('products_page'))

# --------------------------------------------------
#  PUBLIC APIs
# --------------------------------------------------

@app.route('/api/products')
def api_products():
    prods = database.get_stock()          # final-only by default
    return (jsonify(prods), 200) if prods else (jsonify({'error': 'No products'}), 404)

# ------------ ACHIZITII API ---------------------------------
@app.route('/api/achizitii/stock')
def api_achizitii_stock():
    if session.get('employee_dept') != 'achizitii':
        return jsonify({'error': 'Not authorized'}), 403
    data = database.get_cheapest_partner_offer()
    return jsonify(data)

@app.route('/api/achizitii/place_order', methods=['POST'])
def api_achizitii_place_order():
    if session.get('employee_dept') != 'achizitii':
        return jsonify({'error': 'Not authorized'}), 403
    items = (request.get_json() or {}).get('items', [])
    emp_id = database.get_employee_id(session['employee'])
    res = database.create_procurement_orders(emp_id, items)
    return (jsonify(res), 200 if res.get('success') else 400)

@app.route('/api/achizitii/my_orders')
def api_achizitii_my_orders():
    if session.get('employee_dept') != 'achizitii':
        return jsonify({'error': 'Not authorized'}), 403
    eid  = database.get_employee_id(session['employee'])
    rows = database.get_partner_orders()
    out  = []
    for o in rows:
        if o['id_employee'] != eid:
            continue
        o['date_fmt'] = o['data'].strftime('%Y-%m-%d %H:%M')
        o['partner']  = database._fetchone_scalar(
            "SELECT name FROM partners WHERE id_partner=%s",
            (o['id_partner'],))
        out.append(o)
    return jsonify(out)

@app.route('/api/place_order', methods=['POST'])
def api_place_order():
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 403
    items = (request.get_json() or {}).get('items', [])
    res = database.place_order(database.get_customer_id(session['user']), items)
    return (jsonify(res), 200 if res.get('success') else 400)

# --------------------------------------------------
#  EMPLOYEE (SALES) APIs
# --------------------------------------------------

@app.route('/api/employee/orders')
def api_employee_orders():
    if session.get('employee_dept') != 'sales':
        return jsonify({'error': 'Not authorized'}), 403
    eid = database.get_employee_id(session['employee'])
    data = database.get_orders_by_employee(eid)
    for o in data:
        o['qty']  = database.get_order_quantity(o['id_order'])
        # new pretty date -------------------------------------------------
        o['date_fmt'] = o['data'].strftime('%Y-%m-%d %H:%M')
    return jsonify(data)

@app.route('/api/employee/update_order', methods=['POST'])
def api_employee_update_order():
    if session.get('employee_dept') != 'sales':
        return jsonify({'error': 'Not authorized'}), 403
    payload = request.get_json() or {}
    res = database.update_order_status(session['employee'], payload.get('order_id'), payload.get('status'))
    return (jsonify(res), 200 if res.get('success') else 400)

# --------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True)
