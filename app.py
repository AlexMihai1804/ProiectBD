import os
import hashlib
import json
import traceback
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
#  AUTH ROUTES (CUSTOMER & EMPLOYEE & PARTNER)
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

@app.route('/partner_login', methods=['GET', 'POST'])
def partner_login():
    error = None
    if request.method == 'POST':
        uname = request.form['username'].strip().lower()
        pwd   = request.form['password']
        if database.verify_partner(uname, pwd):
            session.clear()
            session['partner'] = uname          # mark partner session
            return redirect(url_for('partners_page'))
        error = 'Date invalide'
    return render_template('partner_login.html', error=error)

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

# --- PUBLIC STOCK API (both raw + final) -------------------------------
@app.route('/api/stock')
def api_stock():
    """Return all products; ?final_only=0 keeps raws too (default 1)."""
    final_only = request.args.get('final_only', '1') != '0'
    rows = database.get_stock(final_only=final_only)
    return (jsonify(rows), 200) if rows else (jsonify({'error': 'No products'}), 404)

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

@app.route('/partners')
def partners_page():
    # -- trebuie să fii logat ca partener --
    if 'partner' not in session:
        return redirect(url_for('partner_login'))

    # extrage id-ul partenerului curent
    partner_id = database._fetchone_scalar(
        "SELECT id_partner FROM partners WHERE LOWER(username)=LOWER(%s)",
        (session['partner'],),               # username salvat în sesiune
        key='id_partner'
    )
    if not partner_id:
        return "Partener inexistent", 404

    # trimite id-ul în template
    return render_template('partners.html', partner_id=partner_id)

# API endpoint to list partners
@app.route('/api/partners')
def api_partners():
    partners = database.get_partners()
    return (jsonify(partners), 200) if partners else (jsonify({'error': 'No partners'}), 404)

# Partner products page
@app.route('/partners/<int:partner_id>/products')
def partner_products_page(partner_id):
    # lookup partner name for display
    partner = database.get_partner(partner_id)
    if not partner:
        return "Partener inexistent", 404
    return render_template(
        'partner_products.html',
        partner_id=partner_id,
        partner_name=partner['name']
    )

# API endpoint
@app.route('/api/partners/<int:partner_id>/products')
def api_partner_products(partner_id):
    prods = database.get_partner_products(partner_id)
    print("Products fetched:", prods)
    if prods is None:
        return jsonify({'error': 'Partner not found'}), 404
    return jsonify(prods)

# NEW: accept POST to update/insert partner_products prices
@app.route('/api/partners/<int:partner_id>/products', methods=['POST'])
def api_set_partner_products(partner_id):
    # only the logged-in partner may update their prices
    partner = database.get_partner(partner_id)
    # compare usernames case-insensitively
    if not partner or session.get('partner', '').lower() != partner['username'].lower():
         return jsonify({'error': 'Not authorized'}), 403

    data   = request.get_json() or {}
    prices = data.get('prices', [])

    for item in prices:
        pid   = item.get('id_product')   # ← acesta este id_stock
        price = item.get('price')

        # există deja rând pt (id_stock, id_partner) ?
        database.cursor.execute(
            "SELECT id_product FROM partner_products "
            "WHERE id_stock=%s AND id_partner=%s",
            (pid, partner_id)
        )
        if database.cursor.fetchone():
            database.cursor.execute(
                "UPDATE partner_products "
                "SET price=%s "
                "WHERE id_stock=%s AND id_partner=%s",
                (price, pid, partner_id)
            )
        else:
            database.cursor.execute(
                "INSERT INTO partner_products (id_stock, price, quantity, id_partner) "
                "VALUES (%s, %s, %s, %s)",
                (pid, price, 0, partner_id)
            )

    database.connection.commit()
    return jsonify({'success': True})

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

@app.route('/api/employee/productie/recipes', methods=['GET'])
def get_recipes():
    # only production dept may query
    if session.get('employee_dept') != 'productie':
        return jsonify({'error': 'Not authorized'}), 403

    recipes = database.get_recipes()

    # -------- NEW: one single query instead of dozens -----------------
    stock_rows = database.get_stock(final_only=False)
    stock_map  = {row['id_product']: row for row in stock_rows}
    # ------------------------------------------------------------------

    result = []
    for rec in recipes:
        ingredients = []
        for i in range(1, 6):
            mid = rec.get(f'id_material{i}')
            qty = rec.get(f'quantity_material{i}')
            if mid and qty:
                srow = stock_map.get(mid, {})
                ingredients.append({
                    'name':     srow.get('name', f'ID {mid}'),
                    'quantity': qty,
                    'stock':    srow.get('quantity', 0)
                })

        final = stock_map.get(rec['id_final'], {})
        result.append({
            'id_final':    rec['id_final'],
            'final_name':  final.get('name', f'ID {rec["id_final"]}'),
            'final_stock': final.get('quantity', 0),
            'ingredients': ingredients
        })

    return jsonify(result)

@app.route('/api/employee/productie/recipes', methods=['POST'])
def create_recipe():
    # only production dept allowed
    if session.get('employee_dept') != 'productie':
        return jsonify({'error': 'Not authorized'}), 403

    payload     = request.get_json() or {}
    final_name  = payload.get('final_name')
    ingredients = payload.get('ingredients', [])

    # basic validation
    if not final_name or not isinstance(ingredients, list) or not ingredients:
        return jsonify({'error': 'Invalid input'}), 400

    # delegate to your Database helper
    res = database.add_recipe(final_name, ingredients)
    return (jsonify(res), 200 if res.get('success') else 400)

@app.route('/api/employee/productie/produce', methods=['POST'])
def produce_product():
    # only production dept allowed
    if session.get('employee_dept') != 'productie':
        return jsonify({'error': 'Not authorized'}), 403

    data       = request.get_json() or {}
    recipe_id  = data.get("recipe_id")
    quantity   = data.get("quantity")

    if not recipe_id or not quantity or quantity <= 0:
        return jsonify({"error": "Invalid input"}), 400

    # fetch the FULL recipe row (need all columns)
    database.cursor.execute("SELECT * FROM recipes WHERE id_final = %s", (recipe_id,))
    recipe = database.cursor.fetchone()
    if not recipe:
        return jsonify({"error": "Recipe not found"}), 404

    try:
        with database.connection:
            for i in range(1, 6):
                mat_id   = recipe.get(f'id_material{i}')
                mat_qty  = recipe.get(f'quantity_material{i}')
                if mat_id and mat_qty:
                    need = mat_qty * quantity
                    have = database._fetchone_scalar(
                        "SELECT quantity FROM stock WHERE id_product = %s",
                        (mat_id,)
                    )
                    if have < need:
                        raise ValueError("Insufficient stock for material")
                    database.cursor.execute(
                        "UPDATE stock SET quantity = quantity - %s WHERE id_product = %s",
                        (need, mat_id)
                    )
            # add produced items
            database.cursor.execute(
                "UPDATE stock SET quantity = quantity + %s WHERE id_product = %s",
                (quantity, recipe_id)
            )
        return jsonify({"success": True})
    except Exception as e:
        database.connection.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/admin')
def admin_panel():
    return render_template('admin.html')

# -- PRODUCT -----------------------------------------------------------------
@app.route('/api/products', methods=['POST'])
def api_create_product():
    data = request.get_json(silent=True) or request.form
    name        = data.get('name')
    price       = data.get('price', type=float)
    description = data.get('description', '')
    quantity    = data.get('quantity', type=int)
    ptype       = data.get('type', 'final')
    if not name or price is None or quantity is None:
        return jsonify({'error':'Nume, pret si cantitate sunt obligatorii'}), 400

    try:
        database.cursor.execute(
            "INSERT INTO stock (name,price,description,quantity,type) "
            "VALUES (%s,%s,%s,%s,%s)",
            (name, price, description, quantity, ptype)
        )
        database.connection.commit()
        return jsonify({'success':True}), 201

    except Exception as e:
        database.connection.rollback()
        return jsonify({'error': str(e)}), 500

# -- EMPLOYEE ----------------------------------------------------------------
@app.route('/api/employees', methods=['POST'])
def api_create_employee():
    data = request.get_json(silent=True) or request.form
    print("Employee data received:", data)

    # parse salary explicitly
    try:
        salary = float(data.get('salary', '').strip())
    except Exception:
        salary = None

    name         = data.get('name')
    surname      = data.get('surname')
    username     = data.get('username')
    email        = data.get('email')
    password     = data.get('password')
    department   = data.get('department')
    phone_number = data.get('phone_number','')
    address      = data.get('address','')

    if not all([name, surname, username, email, password,
                department, phone_number, address, salary]):
        return jsonify({'error':'Toate câmpurile sunt obligatorii'}), 400

    try:
        database.cursor.execute(
            """
            INSERT INTO employees
              (name, surname, department, salary,
               email, phone_number, address,
               username, password)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (name, surname, department, salary,
             email, phone_number, address,
             username, password)
        )
        database.connection.commit()
        return jsonify({'success': True}), 201

    except Exception as e:
        # print full traceback to your terminal
        traceback.print_exc()
        database.connection.rollback()
        # also return the exact error so you can see it in the browser
        return jsonify({'error': str(e)}), 500

# -- CUSTOMER ----------------------------------------------------------------
@app.route('/api/customers', methods=['POST'])
def api_create_customer():
    data = request.get_json(silent=True) or request.form
    name     = data.get('name')
    surname = data.get('surname')
    username = data.get('username')
    email    = data.get('email')
    password = data.get('password')
    address  = data.get('address','')
    phone_number   = data.get('phone_number','')
    if not all([name, surname, username, email, password]):
        return jsonify({'error':'Toate campurile sunt obligatorii'}), 400

    # reuse your existing helper if you have one, otherwise do raw INSERT
    
    try:
        database.cursor.execute(
            "INSERT INTO customers (name, surname, username, email, password, address, phone_number) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (name, surname, username, email, password, address, phone_number)
        )
        database.connection.commit()
        return jsonify({'success':True}), 201

    except Exception as e:
        database.connection.rollback()
        return jsonify({'error': str(e)}), 500

# -- PARTNER -----------------------------------------------------------------
@app.route('/api/partners', methods=['POST'])
def api_create_partner():
    data = request.get_json(silent=True) or request.form
    name    = data.get('name')
    username = data.get('username')
    password = data.get('password')
    address = data.get('address','')
    phone_number   = data.get('phone_number','')
    email = data.get('email','')
    if not name:
        return jsonify({'error':'Nume partener obligatoriu'}), 400

    try:
        database.cursor.execute(
            "INSERT INTO partners (name, username, password, address, phone_number, email) VALUES (%s,%s,%s,%s,%s,%s)",
            (name, username, password, address, phone_number, email)
        )
        database.connection.commit()
        return jsonify({'success':True}), 201

    except Exception as e:
        database.connection.rollback()
        return jsonify({'error': str(e)}), 500
    
# -- PARTNER -----------------------------------------------------------------
@app.route('/api/recipes', methods=['POST'])
def api_create_recipe():
    data = request.get_json(silent=True) or request.form

    # 1) parse & validate the “final” product
    try:
        id_final = int(data.get('id_final'))
        final_qty = int(data.get('quantity'))
    except (TypeError, ValueError):
        return jsonify({'error': 'id_final și quantity trebuie numere întregi'}), 400

    # 2) gather up to 5 materiale + cantități
    materials = []
    for i in range(1, 6):
        mat = data.get(f'id_material{i}')
        qty = data.get(f'quantity_material{i}')
        if mat and qty:
            try:
                materials.append((int(mat), int(qty)))
            except ValueError:
                return jsonify({'error': f'Ingredient {i} invalid'}), 400
        else:
            # pad with NULLs if missing
            materials.append((None, None))

    # 3) build column list & values array
    cols = ['id_final', 'quantity']
    vals = [id_final, final_qty]
    for idx, (mid, mqty) in enumerate(materials, start=1):
        cols.append(f'id_material{idx}')
        cols.append(f'quantity_material{idx}')
        vals.append(mid)
        vals.append(mqty)

    placeholders = ','.join(['%s'] * len(vals))
    col_sql      = ','.join(cols)
    sql          = f"INSERT INTO recipes ({col_sql}) VALUES ({placeholders})"

    try:
        database.cursor.execute(sql, tuple(vals))
        database.connection.commit()
        return jsonify({'success': True}), 201

    except Exception as e:
        database.connection.rollback()
        return jsonify({'error': str(e)}), 500

# --------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True)
