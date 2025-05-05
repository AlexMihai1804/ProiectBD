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
            quantity INTEGER NOT NULL CHECK (quantity >= 0)
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
            quantitiy INTEGER NOT NULL,
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
        CREATE TRIGGER trg_before_delete_order_content BEFORE DELETE ON order_content FOR EACH ROW EXECUTE FUNCTION trg_before_delete_order_content_fn();
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

    def _fetchone_scalar(self, query, params=(), key=None):
        self.cursor.execute(query, params)
        row = self.cursor.fetchone()
        if row is None:
            return None
        return row[key or list(row.keys())[0]]

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

    def get_stock(self):
        self.cursor.execute("SELECT * FROM stock")
        return self.cursor.fetchall()

    def get_partners(self):
        self.cursor.execute("SELECT * FROM partners")
        return self.cursor.fetchall()

    def get_partner_products(self):
        self.cursor.execute("SELECT * FROM partner_products")
        return self.cursor.fetchall()

    def get_partner_orders(self):
        self.cursor.execute("SELECT * FROM partner_orders")
        return self.cursor.fetchall()

    def get_partner_order_content(self):
        self.cursor.execute("SELECT * FROM partner_order_content")
        return self.cursor.fetchall()

    def get_recipes(self):
        self.cursor.execute("SELECT * FROM recipes")
        return self.cursor.fetchall()

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
            "SELECT 1 FROM customers WHERE username=%s AND password=%s",
            (username, password)
        )
        return self.cursor.fetchone() is not None

    def verify_employee(self, username, password):
        self.cursor.execute(
            "SELECT 1 FROM employees WHERE username=%s AND password=%s",
            (username, password)
        )
        return self.cursor.fetchone() is not None

    def verify_partner(self, username, password):
        self.cursor.execute(
            "SELECT 1 FROM partners WHERE username=%s AND password=%s",
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
        self.cursor.execute(
            "UPDATE customers SET password = %s WHERE username = %s",
            (new_password, username)
        )
        self.connection.commit()
        return {"success": True}

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