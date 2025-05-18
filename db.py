import os
from datetime import datetime
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()


class Database:
    def __init__(self):
        self.connection = psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432")
        )
        self.connection.autocommit = False
        self.cursor = self.connection.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        )
        self.create_tables()
        self.create_triggers()
        # populate with dummy data if tables empty
        self.generate_dummy_data()

    def create_tables(self):
        ddl = """
        CREATE TABLE IF NOT EXISTS employees (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            surname TEXT NOT NULL,
            department TEXT NOT NULL,
            salary NUMERIC(10,2) NOT NULL,
            email TEXT NOT NULL,
            phone_number TEXT NOT NULL,
            address TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS customers (
            id_customer SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            surname TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT NOT NULL,
            address TEXT DEFAULT 'null',
            phone_number TEXT DEFAULT 'null'
        );
        CREATE TABLE IF NOT EXISTS stock (
            id_product SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            price NUMERIC(10,2) NOT NULL,
            description TEXT NOT NULL,
            quantity INTEGER NOT NULL CHECK (quantity >= 0),
            type TEXT NOT NULL DEFAULT 'final'
        );
        CREATE TABLE IF NOT EXISTS orders (
            id_order SERIAL PRIMARY KEY,
            id_client INTEGER NOT NULL REFERENCES customers(id_customer),
            data TIMESTAMPTZ NOT NULL,
            progress TEXT NOT NULL,
            id_employee INTEGER NOT NULL REFERENCES employees(id)
        );
        CREATE TABLE IF NOT EXISTS order_content (
            id_item SERIAL PRIMARY KEY,
            id_order INTEGER NOT NULL REFERENCES orders(id_order) ON DELETE CASCADE,
            id_product INTEGER NOT NULL REFERENCES stock(id_product),
            quantity INTEGER NOT NULL,
            price NUMERIC(10,2) NOT NULL
        );
        CREATE TABLE IF NOT EXISTS recipes (
            id_recipe SERIAL PRIMARY KEY,
            id_final INTEGER NOT NULL REFERENCES stock(id_product),
            quantity INTEGER NOT NULL DEFAULT 1,       -- DEFAULT added
            id_material1 INTEGER NOT NULL REFERENCES stock(id_product),
            quantity_material1 INTEGER NOT NULL,
            id_material2 INTEGER REFERENCES stock(id_product),
            quantity_material2 INTEGER,
            id_material3 INTEGER REFERENCES stock(id_product),
            quantity_material3 INTEGER,
            id_material4 INTEGER REFERENCES stock(id_product),
            quantity_material4 INTEGER,
            id_material5 INTEGER REFERENCES stock(id_product),
            quantity_material5 INTEGER
        );
        CREATE TABLE IF NOT EXISTS partners (
            id_partner SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            address TEXT,
            phone_number TEXT,
            email TEXT
        );
        CREATE TABLE IF NOT EXISTS partner_products (
            id_product SERIAL PRIMARY KEY,
            id_stock INTEGER NOT NULL REFERENCES stock(id_product),
            price NUMERIC(10,2) NOT NULL,
            quantity INTEGER NOT NULL CHECK (quantity >= 0),
            id_partner INTEGER NOT NULL REFERENCES partners(id_partner)
        );
        CREATE TABLE IF NOT EXISTS partner_orders (
            id_order SERIAL PRIMARY KEY,
            id_partner INTEGER NOT NULL REFERENCES partners(id_partner),
            data TIMESTAMPTZ NOT NULL,
            status TEXT NOT NULL,
            id_employee INTEGER NOT NULL REFERENCES employees(id)
        );
        CREATE TABLE IF NOT EXISTS partner_order_content (
            id SERIAL PRIMARY KEY,
            id_product INTEGER NOT NULL REFERENCES partner_products(id_product),
            id_order INTEGER NOT NULL REFERENCES partner_orders(id_order) ON DELETE CASCADE,
            quantity INTEGER NOT NULL,
            price NUMERIC(10,2) NOT NULL
        );
        """
        self.cursor.execute(ddl)
        # make sure DEFAULT exists when upgrading ------------------------
        self.cursor.execute(
            "ALTER TABLE recipes ALTER COLUMN quantity SET DEFAULT 1"
        )
        # ensure column exists when upgrading an older DB
        self.cursor.execute("ALTER TABLE stock ADD COLUMN IF NOT EXISTS type TEXT NOT NULL DEFAULT 'final'")
        self.connection.commit()

    def create_triggers(self):
        sql = """
        CREATE OR REPLACE FUNCTION trg_before_insert_order_content_fn() RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            IF (SELECT quantity FROM stock WHERE id_product = NEW.id_product) < NEW.quantity THEN
                RAISE EXCEPTION 'Insufficient stock';
            END IF;
            UPDATE stock SET quantity = quantity - NEW.quantity WHERE id_product = NEW.id_product;
            RETURN NEW;
        END; $$;
        DROP TRIGGER IF EXISTS trg_before_insert_order_content ON order_content;
        CREATE TRIGGER trg_before_insert_order_content BEFORE INSERT ON order_content FOR EACH ROW EXECUTE FUNCTION trg_before_insert_order_content_fn();
        CREATE OR REPLACE FUNCTION trg_before_update_order_content_fn() RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.quantity > OLD.quantity AND (SELECT quantity FROM stock WHERE id_product = NEW.id_product) < (NEW.quantity - OLD.quantity) THEN
                RAISE EXCEPTION 'Insufficient stock';
            END IF;
            UPDATE stock SET quantity = quantity - (NEW.quantity - OLD.quantity) WHERE id_product = NEW.id_product;
            RETURN NEW;
        END; $$;
        DROP TRIGGER IF EXISTS trg_before_update_order_content ON order_content;
        CREATE TRIGGER trg_before_update_order_content BEFORE UPDATE OF quantity ON order_content FOR EACH ROW EXECUTE FUNCTION trg_before_update_order_content_fn();
        CREATE OR REPLACE FUNCTION trg_before_delete_order_content_fn() RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            UPDATE stock SET quantity = quantity + OLD.quantity WHERE id_product = OLD.id_product;
            RETURN OLD;
        END; $$;
        DROP TRIGGER IF EXISTS trg_before_delete_order_content ON order_content;
        CREATE OR REPLACE FUNCTION trg_before_insert_partner_order_content_fn() RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            IF (SELECT quantity FROM partner_products WHERE id_product = NEW.id_product) < NEW.quantity THEN
                RAISE EXCEPTION 'Insufficient stock';
            END IF;
            UPDATE partner_products SET quantity = quantity - NEW.quantity WHERE id_product = NEW.id_product;
            RETURN NEW;
        END; $$;
        DROP TRIGGER IF EXISTS trg_before_insert_partner_order_content ON partner_order_content;
        CREATE TRIGGER trg_before_insert_partner_order_content BEFORE INSERT ON partner_order_content FOR EACH ROW EXECUTE FUNCTION trg_before_insert_partner_order_content_fn();
        CREATE OR REPLACE FUNCTION trg_before_update_partner_order_content_fn() RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.quantity > OLD.quantity AND (SELECT quantity FROM partner_products WHERE id_product = NEW.id_product) < (NEW.quantity - OLD.quantity) THEN
                RAISE EXCEPTION 'Insufficient stock';
            END IF;
            UPDATE partner_products SET quantity = quantity - (NEW.quantity - OLD.quantity) WHERE id_product = NEW.id_product;
            RETURN NEW;
        END; $$;
        DROP TRIGGER IF EXISTS trg_before_update_partner_order_content ON partner_order_content;
        CREATE TRIGGER trg_before_update_partner_order_content BEFORE UPDATE OF quantity ON partner_order_content FOR EACH ROW EXECUTE FUNCTION trg_before_update_partner_order_content_fn();
        CREATE OR REPLACE FUNCTION trg_before_delete_partner_order_content_fn() RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            UPDATE partner_products SET quantity = quantity + OLD.quantity WHERE id_product = OLD.id_product;
            RETURN OLD;
        END; $$;
        DROP TRIGGER IF EXISTS trg_before_delete_partner_order_content ON partner_order_content;
        CREATE TRIGGER trg_before_delete_partner_order_content BEFORE DELETE ON partner_order_content FOR EACH ROW EXECUTE FUNCTION trg_before_delete_partner_order_content_fn();
        """
        self.cursor.execute(sql)
        self.connection.commit()

        # NEW – when a partner order becomes completed increase stock
        self.cursor.execute("""
        CREATE OR REPLACE FUNCTION trg_after_update_partner_order_status_fn()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.status = 'completed' AND OLD.status <> 'completed' THEN
                INSERT INTO stock (id_product,name,price,description,quantity,type)
                SELECT s.id_product, s.name, s.price, s.description,
                       poc.quantity, s.type
                FROM partner_order_content poc
                JOIN partner_products pp ON pp.id_product = poc.id_product
                JOIN stock s ON s.id_product = pp.id_stock
                WHERE poc.id_order = NEW.id_order
                ON CONFLICT (id_product) DO
                  UPDATE SET quantity = stock.quantity + EXCLUDED.quantity;
            END IF;
            RETURN NEW;
        END; $$;
        DROP TRIGGER IF EXISTS trg_after_update_partner_order_status
            ON partner_orders;
        CREATE TRIGGER trg_after_update_partner_order_status
        AFTER UPDATE OF status ON partner_orders
        FOR EACH ROW EXECUTE FUNCTION trg_after_update_partner_order_status_fn();
        """)
        self.connection.commit()

    # -------- NEW: private helper for read-only queries -------------
    def _dict_cur(self):
        """Return a fresh RealDictCursor (auto-closed via context-manager)."""
        return self.connection.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        )

    # ------------------------ patched helpers -----------------------

    def _fetchone_scalar(self, query, params=(), key=None):
        with self._dict_cur() as cur:          # ← use dedicated cursor
            cur.execute(query, params)
            row = cur.fetchone()
            if row is None:
                return None
            return row[key or list(row.keys())[0]]

    # ---------- stock helpers ----------
    def get_stock(self, final_only: bool = True):
        """
        Return stock items. If final_only=True, filter type='final'.
        Uses its own cursor so it never interferes with other result sets.
        """
        with self._dict_cur() as cur:          # ← independent cursor
            if final_only:
                cur.execute("SELECT * FROM stock WHERE type='final'")
            else:
                cur.execute("SELECT * FROM stock")
            return cur.fetchall()

    def get_cheapest_partner_offer(self):
        """
        For every product return quantity on hand, cheapest partner price
        and partner *name* (not id).
        """
        self.cursor.execute(
            """
            SELECT s.id_product,
                   s.name,
                   s.quantity,
                   pp.price             AS partner_price,
                   pr.name              AS partner_name
            FROM stock s
            LEFT JOIN LATERAL (
                SELECT price, id_partner
                FROM partner_products
                WHERE id_stock = s.id_product
                ORDER BY price ASC
                LIMIT 1
            ) pp ON TRUE
            LEFT JOIN partners pr ON pr.id_partner = pp.id_partner
            ORDER BY s.id_product
            """
        )
        return self.cursor.fetchall()

    def get_employees(self):
        self.cursor.execute("SELECT * FROM employees")
        return self.cursor.fetchall()

    def get_customers(self):
        self.cursor.execute("SELECT * FROM customers")
        return self.cursor.fetchall()

    def get_orders(self):
        self.cursor.execute("SELECT * FROM orders")
        return self.cursor.fetchall()

    def get_order_content(self):
        self.cursor.execute("SELECT * FROM order_content")
        return self.cursor.fetchall()

    def get_partners(self):
        self.cursor.execute("SELECT * FROM partners")
        return self.cursor.fetchall()
    
    def get_partner(self, partner_id):
        self.cursor.execute(
            "SELECT * FROM partners WHERE id_partner = %s",
            (partner_id,)
        )
        return self.cursor.fetchone()
    
    def get_partner_products(self, partner_id: int):
        """
        Return a list of dicts like
          { 'id_product': 1, 'name': 'Laptop', 'price': 2600.0, 'quantity': 5 }
        for every row in partner_products joined to stock.
        """
        sql = """
        SELECT
          pp.id_stock   AS id_product,
          s.name        AS name,
          pp.price      AS price,
          pp.quantity   AS quantity
        FROM partner_products pp
        JOIN stock s
          ON pp.id_stock = s.id_product
        WHERE pp.id_partner = %s
        """
        # execute the query
        self.cursor.execute(sql, (partner_id,))
        rows = self.cursor.fetchall()  # list of tuples
        # Directly return the rows as they are already RealDictRow objects
        return rows

    def get_partners_products(self):
        self.cursor.execute("SELECT * FROM partner_products")
        return self.cursor.fetchall()

    def get_partner_orders(self):
        self.cursor.execute("SELECT * FROM partner_orders")
        return self.cursor.fetchall()

    def get_partner_order_content(self):
        self.cursor.execute("SELECT * FROM partner_order_content")
        return self.cursor.fetchall()

    def get_recipes(self):
        """Fetch all recipes (dedicated cursor to avoid clobbering)."""
        with self._dict_cur() as cur:
            cur.execute("SELECT * FROM recipes")
            return cur.fetchall()

    def get_order_quantity(self, order_id):
        q = self._fetchone_scalar(
            "SELECT SUM(quantity) AS qty FROM order_content WHERE id_order = %s",
            (order_id,),
            "qty"
        )
        return q or 0

    def get_partner_order_quantity(self, order_id):
        q = self._fetchone_scalar(
            "SELECT SUM(quantity) AS qty FROM partner_order_content WHERE id_order = %s",
            (order_id,),
            "qty"
        )
        return q or 0

    def verify_customer(self, username, password):
        self.cursor.execute(
            "SELECT 1 FROM customers WHERE LOWER(username)=LOWER(%s) AND password=%s",
            (username, password)
        )
        return self.cursor.fetchone() is not None

    def verify_employee(self, username, password):
        self.cursor.execute(
            "SELECT 1 FROM employees WHERE LOWER(username)=LOWER(%s) AND password=%s",
            (username, password)
        )
        return self.cursor.fetchone() is not None

    def verify_partner(self, username, password):
        self.cursor.execute(
            "SELECT 1 FROM partners "
            "WHERE LOWER(username)=LOWER(%s) "
            "  AND LOWER(password)=LOWER(%s)",
            (username, password)
        )
        return self.cursor.fetchone() is not None

    def get_least_busy_employee(self, department):
        self.cursor.execute(
            """
            SELECT e.id
            FROM employees e
            LEFT JOIN orders o ON o.id_employee = e.id AND o.progress <> 'completed'
            LEFT JOIN partner_orders po ON po.id_employee = e.id AND po.status <> 'completed'
            WHERE e.department = %s
            GROUP BY e.id
            ORDER BY COUNT(o.id_order) + COUNT(po.id_order) ASC
            LIMIT 1
            """,
            (department,)
        )
        row = self.cursor.fetchone()
        return row["id"] if row else None

    def place_order(self, customer_id, item_list):
        if not item_list:
            return {"error": "Empty item list"}
        employee_id = self.get_least_busy_employee("sales")
        if not employee_id:
            return {"error": "No available employee"}
        try:
            with self.connection:
                now = datetime.utcnow()
                self.cursor.execute(
                    "INSERT INTO orders (id_client, data, progress, id_employee) VALUES (%s, %s, %s, %s) RETURNING id_order",
                    (customer_id, now, "pending", employee_id)
                )
                order_id = self.cursor.fetchone()["id_order"]
                for pid, qty in item_list:
                    if qty <= 0:
                        raise ValueError("Invalid quantity")
                    price = self._fetchone_scalar(
                        "SELECT price FROM stock WHERE id_product = %s",
                        (pid,)
                    )
                    if price is None:
                        raise LookupError("Product not found")
                    self.cursor.execute(
                        "INSERT INTO order_content (id_order, id_product, quantity, price) VALUES (%s, %s, %s, %s)",
                        (order_id, pid, qty, price)
                    )
            return {"success": True, "order_id": order_id}
        except Exception as exc:
            self.connection.rollback()
            return {"error": str(exc)}

    def place_partner_order(self, partner_id, item_list):
        if not item_list:
            return {"error": "Empty item list"}
        employee_id = self.get_least_busy_employee("sales")
        if not employee_id:
            return {"error": "No available employee"}
        try:
            with self.connection:
                now = datetime.utcnow()
                self.cursor.execute(
                    "INSERT INTO partner_orders (id_partner, data, status, id_employee) VALUES (%s, %s, %s, %s) RETURNING id_order",
                    (partner_id, now, "pending", employee_id)
                )
                order_id = self.cursor.fetchone()["id_order"]
                for pid, qty in item_list:
                    if qty <= 0:
                        raise ValueError("Invalid quantity")
                    price = self._fetchone_scalar(
                        "SELECT price FROM partner_products WHERE id_product = %s",
                        (pid,)
                    )
                    if price is None:
                        raise LookupError("Product not found")
                    self.cursor.execute(
                        "INSERT INTO partner_order_content (id_product, id_order, quantity, price) VALUES (%s, %s, %s, %s)",
                        (pid, order_id, qty, price)
                    )
            return {"success": True, "order_id": order_id}
        except Exception as exc:
            self.connection.rollback()
            return {"error": str(exc)}

    def reset_customer_password(self, username, new_password):
        self.cursor.execute(
            "SELECT 1 FROM customers WHERE username = %s", (username,)
        )
        if self.cursor.fetchone() is None:
            return {"error": "User not found"}
        try:
            self.cursor.execute(
                "UPDATE customers SET password = %s WHERE username = %s",
                (new_password, username)
            )
            self.connection.commit()
            return {"success": True}
        
        except Exception as exc:
            self.connection.rollback()
            return {"error": str(exc)}

    def reset_employee_password(self, username, new_password):
        self.cursor.execute(
            "SELECT 1 FROM employees WHERE username = %s", (username,)
        )
        if self.cursor.fetchone() is None:
            return {"error": "User not found"}
        self.cursor.execute(
            "UPDATE employees SET password = %s WHERE username = %s",
            (new_password, username)
        )
        self.connection.commit()
        return {"success": True}

    def search_product_by_name(self, name):
        self.cursor.execute(
            "SELECT * FROM stock WHERE LOWER(name) LIKE LOWER(%s)",
            (f"%{name}%",)
        )
        return self.cursor.fetchall()

    def get_orders_by_customer(self, customer_id):
        self.cursor.execute(
            "SELECT * FROM orders WHERE id_client = %s ORDER BY data DESC",
            (customer_id,)
        )
        return self.cursor.fetchall()

    def get_orders_by_status(self, status):
        self.cursor.execute(
            "SELECT * FROM orders WHERE progress = %s ORDER BY data DESC",
            (status,)
        )
        return self.cursor.fetchall()

    def get_customer_id(self, username):
        """
        Return id_customer for a given username or None.
        """
        return self._fetchone_scalar(
            "SELECT id_customer FROM customers WHERE LOWER(username)=LOWER(%s)",
            (username,),
            key="id_customer"
        )

    def create_customer(self, name, surname, username, password, email, address='', phone_number=''):
        """
        Insert a new customer. Returns {"success":True} or {"error": "..."}.
        """
        try:
            self.cursor.execute(
                "INSERT INTO customers (name,surname,username,password,email,address,phone_number) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (name, surname, username, password, email, address, phone_number)
            )
            self.connection.commit()
            return {"success": True}
        except Exception as exc:
            self.connection.rollback()
            return {"error": str(exc)}

    def get_customer_by_username(self, username):
        """
        Return full customer record or None.
        """
        self.cursor.execute(
            "SELECT id_customer, name, surname, username, email, address, phone_number "
            "FROM customers WHERE username = %s",
            (username,)
        )
        return self.cursor.fetchone()

    def get_customer_by_id(self, cid):
        """
        Return customer record for a given id_customer.
        """
        self.cursor.execute(
            "SELECT id_customer, name, surname, email, address, phone_number "
            "FROM customers WHERE id_customer = %s",
            (cid,)
        )
        return self.cursor.fetchone()

    def get_employee_by_username(self, username):
        self.cursor.execute(
            "SELECT * FROM employees WHERE username=%s",
            (username,)
        )
        return self.cursor.fetchone()

    def generate_dummy_data(self):
        """
        Populate employees, customers, stock, partners, partner_products,
        orders, order_content, partner_orders, partner_order_content, recipes.
        """
        # seed employees
        if self._fetchone_scalar("SELECT COUNT(*) FROM employees") == 0:
            employees = [
                ("Ion",    "Popescu",  "sales",      3500.00, "ion@example.com",    "0712345678", "Str. A, Nr.1", "ionp",   "pass123"),
                ("Maria",  "Ionescu",  "sales",      3600.00, "maria@example.com",  "0723456789", "Str. B, Nr.2", "mariai", "pass123"),
            ]
            self.cursor.executemany(
                "INSERT INTO employees (name,surname,department,salary,email,phone_number,address,username,password) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                employees
            )

        # always ensure achizitii employees exist
        achizitii = [
            ("George", "Enache", "achizitii", 3400.00, "george@ex.com", "0731231231", "Str. C 3", "geoe", "pass123"),
            ("Ana",    "Popa",   "achizitii", 3450.00, "ana.p@ex.com",  "0743213213", "Str. D 4", "anap", "pass123")
        ]
        self.cursor.executemany(
            "INSERT INTO employees (name,surname,department,salary,email,phone_number,address,username,password) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT (username) DO NOTHING",
            achizitii
        )
        
        
        # always ensure productie employees exist
        productie = [
            ("Calin", "Poenaru", "productie", 4000.00, "calin@ex.com", "0736231231", "Str. C 3", "calin_p", "pass123"),
            ("Sana",   "Alexa",  "productie", 4050.00, "sana@ex.com",  "0745213213", "Str. D 4", "sana_a", "pass123")
        ]
        self.cursor.executemany(
            "INSERT INTO employees (name,surname,department,salary,email,phone_number,address,username,password) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT (username) DO NOTHING",
            productie
        )

        # seed customers
        if self._fetchone_scalar("SELECT COUNT(*) FROM customers") == 0:
            customers = [
                ("Andrei", "Georgescu", "andreg", "pwd1", "andrei@example.com", "Bd X 10", "0730000000"),
                ("Elena", "Marinescu", "elenam", "pwd2", "elena@example.com", "Str Y 20", "0740000000")
            ]
            self.cursor.executemany(
                "INSERT INTO customers (name,surname,username,password,email,address,phone_number) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                customers
            )
        # seed stock
        if self._fetchone_scalar("SELECT COUNT(*) FROM stock") == 0:
            products = [
                ("Laptop",  2500.00, "High-end laptop", 10, "final"),
                ("Telefon", 1500.00, "Smartphone modern", 20, "final"),
                ("Mouse",    100.00, "Wireless mouse",  50, "final"),
                ("Șurub",      1.00, "Materie primă",   500, "materie"),
            ]
            self.cursor.executemany(
                "INSERT INTO stock (name,price,description,quantity,type) VALUES (%s,%s,%s,%s,%s)",
                products
            )
        # seed partners
        if self._fetchone_scalar("SELECT COUNT(*) FROM partners") == 0:
            partners = [
                ("Distribuitor A", "distA", "passA", "Str. Distrib A", "0750000001", "a@dist.ro"),
                ("Distribuitor B", "distB", "passB", "Str. Distrib B", "0750000002", "b@dist.ro")
            ]
            self.cursor.executemany(
                "INSERT INTO partners (name,username,password,address,phone_number,email) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                partners
            )

        # seed partner_products
        if self._fetchone_scalar("SELECT COUNT(*) FROM partner_products") == 0:
            # map first stock ids to partners
            partner_products = [
                (1, 2600.00, 5, 1),
                (2, 1550.00, 10, 2)
            ]
            self.cursor.executemany(
                "INSERT INTO partner_products (id_stock,price,quantity,id_partner) "
                "VALUES (%s,%s,%s,%s)",
                partner_products
            )

        # seed orders and order_content
        if self._fetchone_scalar("SELECT COUNT(*) FROM orders") == 0:
            # use first customer and first employee
            cust = self._fetchone_scalar("SELECT id_customer FROM customers LIMIT 1")
            emp  = self._fetchone_scalar("SELECT id FROM employees LIMIT 1")
            now  = datetime.utcnow()
            self.cursor.execute(
                "INSERT INTO orders (id_client,data,progress,id_employee) VALUES (%s,%s,%s,%s) RETURNING id_order",
                (cust, now, "completed", emp)
            )
            oid = self.cursor.fetchone()["id_order"]
            # add one product
            self.cursor.execute(
                "INSERT INTO order_content (id_order,id_product,quantity,price) VALUES (%s,%s,%s,%s)",
                (oid, 1, 1, self._fetchone_scalar("SELECT price FROM stock WHERE id_product=1"))
            )

        # seed partner_orders and partner_order_content
        if self._fetchone_scalar("SELECT COUNT(*) FROM partner_orders") == 0:
            part = self._fetchone_scalar("SELECT id_partner FROM partners LIMIT 1")
            emp  = self._fetchone_scalar("SELECT id FROM employees LIMIT 1")
            now  = datetime.utcnow()
            self.cursor.execute(
                "INSERT INTO partner_orders (id_partner,data,status,id_employee) VALUES (%s,%s,%s,%s) RETURNING id_order",
                (part, now, "pending", emp)
            )
            poid = self.cursor.fetchone()["id_order"]
            # add one partner product
            self.cursor.execute(
                "INSERT INTO partner_order_content (id_product,id_order,quantity,price) VALUES (%s,%s,%s,%s)",
                (1, poid, 2, self._fetchone_scalar("SELECT price FROM partner_products WHERE id_product=1"))
            )

        # seed recipes
        if self._fetchone_scalar("SELECT COUNT(*) FROM recipes") == 0:
            # final product id 1 made from product ids 2 and 3
            print("Inserting dummy recipe data...")
            self.cursor.execute(
                "INSERT INTO recipes (id_final,quantity,id_material1,quantity_material1,"
                "id_material2,quantity_material2) VALUES (%s,%s,%s,%s,%s,%s)",
                (1, 1, 2, 2, 3, 1)
            )

        self.connection.commit()

    # adjust to case-insensitive lookup
    def get_employee_id(self, username):
        return self._fetchone_scalar(
            "SELECT id FROM employees WHERE LOWER(username)=LOWER(%s)",
            (username,), key='id'
        )

    def get_orders_by_employee(self, emp_id):
        self.cursor.execute(
            "SELECT * FROM orders WHERE id_employee=%s ORDER BY data DESC",
            (emp_id,)
        )
        return self.cursor.fetchall()

    def update_order_status(self, employee_username, order_id, new_status):
        allowed = {'pending', 'processing', 'shipped', 'completed', 'cancelled'}
        if new_status not in allowed:
            return {'error': 'Invalid status'}

        emp_id = self.get_employee_id(employee_username)
        if not emp_id:
            return {'error': 'Employee not found'}

        self.cursor.execute(
            "SELECT progress FROM orders WHERE id_order=%s AND id_employee=%s",
            (order_id, emp_id)
        )
        row = self.cursor.fetchone()
        if not row:
            return {'error': 'Order not found or not assigned to you'}
        old_status = row['progress']
        if old_status == 'cancelled':
            return {'error': 'Order already cancelled'}
        if old_status == new_status:
            return {'success': True}

        try:
            with self.connection:
                # dacă anulează – repunem în stoc
                if new_status == 'cancelled':
                    self.cursor.execute(
                        "SELECT id_product, quantity FROM order_content WHERE id_order=%s",
                        (order_id,)
                    )
                    for item in self.cursor.fetchall():
                        self.cursor.execute(
                            "UPDATE stock SET quantity = quantity + %s WHERE id_product = %s",
                            (item['quantity'], item['id_product'])
                        )
                self.cursor.execute(
                    "UPDATE orders SET progress = %s WHERE id_order = %s",
                    (new_status, order_id)
                )
            return {'success': True}
        except Exception as exc:
            self.connection.rollback()
            return {'error': str(exc)}

    def get_order_items(self, order_id):
        """
        Return list of items (name, quantity, price) for one order.
        """
        self.cursor.execute(
            """SELECT s.name, oc.quantity, oc.price
               FROM order_content oc
               JOIN stock s ON s.id_product = oc.id_product
               WHERE oc.id_order = %s""",
            (order_id,)
        )
        return self.cursor.fetchall()

    def get_partner_order_items(self, order_id):
        """
        Return list of rows for a partner order:
        name, quantity, price.
        """
        self.cursor.execute("""
            SELECT s.name, poc.quantity, poc.price
            FROM partner_order_content poc
            JOIN partner_products pp ON pp.id_product = poc.id_product
            JOIN stock s            ON s.id_product = pp.id_stock
            WHERE poc.id_order = %s
        """, (order_id,))
        return self.cursor.fetchall()

    # ---------- procurement helper ----------
    def create_procurement_orders(self, employee_id: int, item_list: list):
        """
        Receive list[(product_id, qty)], splits them per cheapest partner
        and creates one partner_order/partner. Returns {"success":True}.
        """
        if not item_list:
            return {"error": "Empty list"}
        try:
            with self.connection:
                # map product -> (partner_id, price)
                self.cursor.execute("""
                    SELECT pp.id_stock, pp.id_partner, pp.price
                    FROM partner_products pp
                    JOIN (
                        SELECT id_stock, MIN(price) AS p
                        FROM partner_products
                        GROUP BY id_stock
                    ) m ON m.id_stock = pp.id_stock AND m.p = pp.price
                """)
                cheapest = {(r['id_stock']): (r['id_partner'], r['price'])
                            for r in self.cursor.fetchall()}

                # group items by partner
                grouped = {}
                for pid, qty in item_list:
                    if pid not in cheapest:
                        raise LookupError("No supplier for product")
                    partner, price = cheapest[pid]
                    grouped.setdefault(partner, []).append((pid, qty, price))

                for partner_id, rows in grouped.items():
                    now = datetime.utcnow()
                    self.cursor.execute(
                        "INSERT INTO partner_orders (id_partner,data,status,id_employee) "
                        "VALUES (%s,%s,'pending',%s) RETURNING id_order",
                        (partner_id, now, employee_id)
                    )
                    poid = self.cursor.fetchone()['id_order']
                    for pid, qty, price in rows:
                        self.cursor.execute(
                            "INSERT INTO partner_order_content (id_product,id_order,quantity,price) "
                            "VALUES (%s,%s,%s,%s)",
                            (self._pid_from_stock(pid), poid, qty, price)
                        )
            return {"success": True}
        except Exception as exc:
            self.connection.rollback()
            return {"error": str(exc)}

    def _pid_from_stock(self, stock_id):
        """return partner_products.id_product for given stock id_stock."""
        return self._fetchone_scalar(
            "SELECT id_product FROM partner_products WHERE id_stock=%s LIMIT 1",
            (stock_id,), 'id_product')
    
    def add_user(self, user_type, data):
        if user_type not in ["employee", "customer", "partner"]:
            return {"error" : "Invalid user type"}
    
        try:
            if user_type == "employee":
                self.cursor.execute(
                    """
                    INSERT INTO employees (name, surname, department, salary, email, phone_number, address, username, password)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        data["name"],
                        data["surname"],
                        data["department"],
                        data["salary"],
                        data["email"],
                        data["phone_number"],
                        data["address"],
                        data["username"],
                        data["password"]
                    )
                )
            
            elif user_type == "customer":
                self.cursor.execute(
                    """
                    INSERT INTO customers (name, surname, username, password, email, address, phone_number)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        data["name"],
                        data["surname"],
                        data["username"],
                        data["password"],
                        data["email"],
                        data.get("address", "null"),
                        data.get("phone_number", "null")
                    )
                )
                
            elif user_type == "partner":
                self.cursor.execute(
                    """
                    INSERT INTO partners (name, username, password, address, phone_number, email)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        data["name"],
                        data["username"],
                        data["password"],
                        data.get("address"),
                        data.get("phone_number"),
                        data.get("email")
                    )
                )
            
            self.connection.commit()
            return {"succes" : True}
    
        except psycopg2.IntegrityError as e:
            self.connection.rollback()
            return {"error": "Username already exists"}
        
        except Exception as e:
            self.connection.rollback()
            return{"error" : str(e)}

    def add_recipe(self, final_name: str, ingredients: list[dict]):
        """
        Insert a new recipe; always stores a base quantity (=1) and
        guarantees DB rollback on failure.
        """
        try:
            with self.connection:
                id_final = self._fetchone_scalar(
                    "SELECT id_product FROM stock WHERE name=%s AND type='final'",
                    (final_name,))
                if not id_final:
                    return {'success': False, 'error': 'Final product not found'}

                seen = set()
                cols = ['id_final', 'quantity']   # ← base quantity column
                vals = [id_final, 1]              # ← default = 1

                for idx, ing in enumerate(ingredients[:5], start=1):
                    mat_id = self._fetchone_scalar(
                        "SELECT id_product FROM stock WHERE name=%s AND type<>'final'",
                        (ing['name'],))
                    if not mat_id:
                        raise ValueError(f"Ingredient not found: {ing['name']}")
                    if mat_id in seen:
                        raise ValueError(f"Ingredient duplicated: {ing['name']}")
                    seen.add(mat_id)

                    cols += [f"id_material{idx}", f"quantity_material{idx}"]
                    vals += [mat_id, ing['quantity']]

                # pad unused slots ---------------------------------------
                for idx in range(len(ingredients)+1, 6):
                    cols += [f"id_material{idx}", f"quantity_material{idx}"]
                    vals += [None, None]

                sql = f"INSERT INTO recipes ({', '.join(cols)}) VALUES ({', '.join(['%s']*len(vals))})"
                self.cursor.execute(sql, tuple(vals))

            return {'success': True, 'recipe_id': id_final}

        except Exception as e:
            self.connection.rollback()          # ensure clean state
            return {'success': False, 'error': str(e)}

