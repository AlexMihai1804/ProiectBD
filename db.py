import os
from datetime import datetime

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()


class Database:
    def __init__(self):
        # Conectare la baza de date
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
        # Creare tabele și trigger-e
        self.create_tables()
        self.create_triggers()
        # Popularea cu date de test
        self.generate_dummy_data()

    def create_tables(self):
        # Creează toate tabelele + alter şi index în aceeaşi instrucţiune
        sql = """
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
            name TEXT NOT NULL UNIQUE,
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
            quantity INTEGER NOT NULL DEFAULT 1,
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
        self.cursor.execute(sql)
        self.connection.commit()

    def create_triggers(self):
        # Creeaza trigger-e pentru actualizarea stocului la inserare, actualizare și ștergere
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

    def _dict_cur(self):
        # Creeaza un cursor cu suport pentru dict-uri
        return self.connection.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        )

    # === new partner helpers ===
    def get_partner_id(self, username: str):
        """Returnează id-ul partenerului sau None."""
        with self._dict_cur() as cur:
            cur.execute(
                "SELECT id_partner FROM partners WHERE LOWER(username)=LOWER(%s)",
                (username,))
            row = cur.fetchone()
            return row["id_partner"] if row else None

    def get_partner_name(self, pid: int):
        """Returnează numele partenerului sau None."""
        with self._dict_cur() as cur:
            cur.execute("SELECT name FROM partners WHERE id_partner=%s", (pid,))
            row = cur.fetchone()
            return row["name"] if row else None
    # ===========================

    def get_stock(self, final_only=True):
        # returnează toate produsele din stoc
        with self._dict_cur() as cur:
            if final_only:
                cur.execute("SELECT * FROM stock WHERE type='final'")
            else:
                cur.execute("SELECT * FROM stock")
            return cur.fetchall()

    def get_cheapest_partner_offer(self):
        # returnează cele mai ieftine oferte de la parteneri pentru fiecare produs
        self.cursor.execute(
            """
            SELECT s.id_product,
                   s.name,
                   s.quantity,
                   s.type,
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
        # Listă completă de angajați.
        self.cursor.execute("SELECT * FROM employees")
        return self.cursor.fetchall()

    def get_customers(self):
        # Listă completă de clienți.
        self.cursor.execute("SELECT * FROM customers")
        return self.cursor.fetchall()

    def get_orders(self):
        # Comenzile clienților.
        self.cursor.execute("SELECT * FROM orders")
        return self.cursor.fetchall()

    def get_order_content(self):
        # Articolele din comenzile clienților.
        self.cursor.execute("SELECT * FROM order_content")
        return self.cursor.fetchall()

    def get_partners(self):
        # Listă completă de parteneri.
        self.cursor.execute("SELECT * FROM partners")
        return self.cursor.fetchall()

    def get_partner(self, partner_id):
        # Datele unui partener cu un anumit ID.
        self.cursor.execute(
            "SELECT * FROM partners WHERE id_partner = %s",
            (partner_id,)
        )
        return self.cursor.fetchone()

    def get_partner_products(self, partner_id):
        # Produsele unui partener dat.
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
        self.cursor.execute(sql, (partner_id,))
        rows = self.cursor.fetchall()
        return rows

    def get_partners_products(self):
        # Toate produsele partenerilor.
        self.cursor.execute("SELECT * FROM partner_products")
        return self.cursor.fetchall()

    def get_partner_orders(self):
        # Comenzile către parteneri.
        self.cursor.execute("SELECT * FROM partner_orders")
        return self.cursor.fetchall()

    def get_partner_order_content(self):
        # Articolele din comenzile către parteneri.
        self.cursor.execute("SELECT * FROM partner_order_content")
        return self.cursor.fetchall()

    def get_recipes(self):
        # Rețetele existente.
        with self._dict_cur() as cur:
            cur.execute("SELECT * FROM recipes")
            return cur.fetchall()

    def get_order_quantity(self, order_id):
        # Cantitatea totală dintr-o comandă.
        with self._dict_cur() as cur:
            cur.execute(
                "SELECT SUM(quantity) AS qty FROM order_content WHERE id_order = %s",
                (order_id,))
            row = cur.fetchone()
            q = row["qty"] if row else None
        return q or 0

    def get_partner_order_quantity(self, order_id):
        # Cantitatea totală dintr-o comandă către partener.
        with self._dict_cur() as cur:
            cur.execute(
                "SELECT SUM(quantity) AS qty FROM partner_order_content WHERE id_order = %s",
                (order_id,))
            row = cur.fetchone()
            q = row["qty"] if row else None
        return q or 0

    def verify_customer(self, username, password):
        # verficare parolă client
        self.cursor.execute(
            "SELECT 1 FROM customers WHERE LOWER(username)=LOWER(%s) AND password=%s",
            (username, password)
        )
        return self.cursor.fetchone() is not None

    def verify_employee(self, username, password):
        # verificare parolă angajat
        self.cursor.execute(
            "SELECT 1 FROM employees WHERE LOWER(username)=LOWER(%s) AND password=%s",
            (username, password)
        )
        return self.cursor.fetchone() is not None

    def verify_partner(self, username, password):
        # verificare parolă partener
        self.cursor.execute(
            "SELECT 1 FROM partners "
            "WHERE LOWER(username)=LOWER(%s) "
            "  AND LOWER(password)=LOWER(%s)",
            (username, password)
        )
        return self.cursor.fetchone() is not None

    def reset_customer_password(self, username, new_password):
        # Resetare parolă client.
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
        # Resetare parolă angajat.
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
        # Căutare produs după nume.
        self.cursor.execute(
            "SELECT * FROM stock WHERE LOWER(name) LIKE LOWER(%s)",
            (f"%{name}%",)
        )
        return self.cursor.fetchall()

    def get_orders_by_customer(self, customer_id):
        # Comenzile unui client dat.
        self.cursor.execute(
            "SELECT * FROM orders WHERE id_client = %s ORDER BY data DESC",
            (customer_id,)
        )
        return self.cursor.fetchall()

    def get_orders_by_status(self, status):
        # Comenzile cu un anumit status.
        self.cursor.execute(
            "SELECT * FROM orders WHERE progress = %s ORDER BY data DESC",
            (status,)
        )
        return self.cursor.fetchall()

    def get_customer_id(self, username):
        # id-ul clientului cu un anumit username.
        with self._dict_cur() as cur:
            cur.execute(
                "SELECT id_customer FROM customers WHERE LOWER(username)=LOWER(%s)",
                (username,))
            row = cur.fetchone()
            return row['id_customer'] if row else None

    def create_customer(self, name, surname, username, password, email, address='', phone_number=''):
        # adaugă un client în baza de date.
        self.cursor.execute(
            "INSERT INTO customers (name,surname,username,password,email,address,phone_number) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (name, surname, username, password, email, address, phone_number)
        )
        self.connection.commit()
        return {"success": True}

    def get_customer_by_username(self, username):
        # datele unui client cu un anumit username.
        self.cursor.execute(
            "SELECT id_customer, name, surname, username, email, address, phone_number "
            "FROM customers WHERE username = %s",
            (username,)
        )
        return self.cursor.fetchone()

    def get_customer_by_id(self, cid):
        # datele unui client cu un anumit id.
        self.cursor.execute(
            "SELECT id_customer, name, surname, email, address, phone_number "
            "FROM customers WHERE id_customer = %s",
            (cid,)
        )
        return self.cursor.fetchone()

    def get_employee_by_username(self, username):
        # datele unui angajat cu un anumit username.
        self.cursor.execute(
            "SELECT * FROM employees WHERE username=%s",
            (username,)
        )
        return self.cursor.fetchone()

    def generate_dummy_data(self):
        # adaugă date de test în baza de date.
        try:
            with self._dict_cur() as cur:
                cur.execute("SELECT COUNT(*) AS cnt FROM employees")
                if cur.fetchone()['cnt'] == 0:
                    employees = [
                        ("Ion", "Popescu", "sales", 3500.00, "ion@example.com", "0712345678", "Str. A, Nr.1", "ionp",
                         "pass123"),
                        ("Maria", "Ionescu", "sales", 3600.00, "maria@example.com", "0723456789", "Str. B, Nr.2", "mariai",
                         "pass123"),
                    ]
                    self.cursor.executemany(
                        "INSERT INTO employees (name,surname,department,salary,email,phone_number,address,username,password) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        employees
                    )
                achizitii = [
                    (
                        "George", "Enache", "achizitii", 3400.00, "george@ex.com", "0731231231", "Str. C 3", "geoe",
                        "pass123"),
                    ("Ana", "Popa", "achizitii", 3450.00, "ana.p@ex.com", "0743213213", "Str. D 4", "anap", "pass123")
                ]
                self.cursor.executemany(
                    "INSERT INTO employees (name,surname,department,salary,email,phone_number,address,username,password) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (username) DO NOTHING",
                    achizitii
                )
                productie = [
                    ("Calin", "Poenaru", "productie", 4000.00, "calin@ex.com", "0736231231", "Str. C 3", "calin_p",
                     "pass123"),
                    ("Sana", "Alexa", "productie", 4050.00, "sana@ex.com", "0745213213", "Str. D 4", "sana_a", "pass123")
                ]
                self.cursor.executemany(
                    "INSERT INTO employees (name,surname,department,salary,email,phone_number,address,username,password) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (username) DO NOTHING",
                    productie
                )
                with self._dict_cur() as cur:
                    cur.execute("SELECT COUNT(*) AS cnt FROM customers")
                    if cur.fetchone()["cnt"] == 0:
                        customers = [
                            ("Andrei", "Georgescu", "andreg", "pass123", "andrei@example.com", "Bd X 10", "0730000000"),
                            ("Elena", "Marinescu", "elenam", "pass123", "elena@example.com", "Str Y 20", "0740000000")
                        ]
                        self.cursor.executemany(
                            "INSERT INTO customers (name,surname,username,password,email,address,phone_number) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                            customers
                        )
                with self._dict_cur() as cur:
                    cur.execute("SELECT COUNT(*) AS cnt FROM stock")
                    if cur.fetchone()["cnt"] == 0:
                        products = [
                            ("Cola 0.5 L", 2.50, "Băutură răcoritoare", 100, "final"),
                            ("Cola 1 L", 4.00, "Băutură răcoritoare", 80, "final"),
                            ("Orange Soda 0.5 L", 2.50, "Suc portocale carbog.", 120, "final"),
                            ("Lemonade 0.5 L", 2.20, "Limonadă carbog.", 90, "final"),
                            ("Apă carbogazoasă", 0.20, "Materie primă", 1000, "materie"),
                            ("Zahăr", 0.10, "Materie primă", 800, "materie"),
                            ("CO₂", 0.05, "Dioxid de carbon", 2000, "materie"),
                            ("Colorant caramel", 0.15, "Aditiv", 300, "materie"),
                            ("Acid fosforic", 0.08, "Aditiv", 300, "materie"),
                            ("Cofeină", 0.12, "Aditiv", 200, "materie"),
                            ("Aromă portocale", 0.14, "Aromă", 400, "materie"),
                            ("Aromă lămâie", 0.14, "Aromă", 400, "materie"),
                            ("PET 0.5 L", 0.30, "Sticlă plastic", 1000, "materie"),
                            ("PET 1 L", 0.35, "Sticlă plastic", 800, "materie"),
                            ("Capac PET", 0.05, "Capac sticlă", 1800, "materie"),
                            ("Etichetă", 0.04, "Etichetă autoadez.", 2000, "materie"),
                        ]
                        self.cursor.executemany(
                            "INSERT INTO stock (name,price,description,quantity,type) "
                            "VALUES (%s,%s,%s,%s,%s) "
                            "ON CONFLICT (name) DO NOTHING",
                            products
                        )
                with self._dict_cur() as cur:
                    cur.execute("SELECT COUNT(*) AS cnt FROM partners")
                    if cur.fetchone()["cnt"] == 0:
                        partners = [
                            ("Furnizor Ambalaje",  "bottlesupp", "pass123", "Str. Ambalaje 1", "0751000001", "bottle@sup.ro"),
                            ("Furnizor Ingrediente","ingsupp",   "pass123", "Str. Ingred  2", "0752000002", "ing@sup.ro"),
                        ]
                        self.cursor.executemany(
                            "INSERT INTO partners (name,username,password,address,phone_number,email) "
                            "VALUES (%s,%s,%s,%s,%s,%s)",
                            partners
                        )
                with self._dict_cur() as cur:
                    cur.execute("SELECT COUNT(*) AS cnt FROM partner_products")
                    if cur.fetchone()["cnt"] == 0:
                        self.cursor.execute("SELECT id_product, name FROM stock")
                        id_by_name = {r['name']: r['id_product'] for r in self.cursor.fetchall()}
                        self.cursor.execute("SELECT id_partner, username FROM partners")
                        pid_by_user = {r['username']: r['id_partner'] for r in self.cursor.fetchall()}
                        partner_products = [
                            (id_by_name["PET 0.5 L"], 0.32, 10000, pid_by_user["bottlesupp"]),
                            (id_by_name["PET 1 L"], 0.37, 8000, pid_by_user["bottlesupp"]),
                            (id_by_name["Capac PET"], 0.06, 15000, pid_by_user["bottlesupp"]),
                            (id_by_name["Etichetă"], 0.045, 20000, pid_by_user["bottlesupp"]),
                            (id_by_name["Zahăr"], 0.11, 5000, pid_by_user["ingsupp"]),
                            (id_by_name["CO₂"], 0.055, 8000, pid_by_user["ingsupp"]),
                            (id_by_name["Colorant caramel"], 0.17, 3000, pid_by_user["ingsupp"]),
                            (id_by_name["Acid fosforic"], 0.09, 3000, pid_by_user["ingsupp"]),
                            (id_by_name["Cofeină"], 0.13, 2000, pid_by_user["ingsupp"]),
                            (id_by_name["Aromă portocale"], 0.15, 4000, pid_by_user["ingsupp"]),
                            (id_by_name["Aromă lămâie"], 0.15, 4000, pid_by_user["ingsupp"]),
                        ]
                        self.cursor.executemany(
                            "INSERT INTO partner_products (id_stock, price, quantity, id_partner) "
                            "VALUES (%s,%s,%s,%s)",
                            partner_products
                        )
                with self._dict_cur() as cur:
                    cur.execute("SELECT COUNT(*) AS cnt FROM recipes")
                    if cur.fetchone()["cnt"] == 0:
                        self.cursor.execute("SELECT id_product,name FROM stock")
                        id_by_name = {r['name']: r['id_product'] for r in self.cursor.fetchall()}
                        recipes_rows = [
                            (id_by_name["Cola 0.5 L"], 1,
                             id_by_name["Apă carbogazoasă"], 1,
                             id_by_name["Zahăr"], 1,
                             id_by_name["Colorant caramel"], 1,
                             id_by_name["Acid fosforic"], 1,
                             id_by_name["Cofeină"], 1),
                            (id_by_name["Cola 1 L"], 1,
                             id_by_name["Apă carbogazoasă"], 2,
                             id_by_name["Zahăr"], 2,
                             id_by_name["Colorant caramel"], 2,
                             id_by_name["Acid fosforic"], 2,
                             id_by_name["Cofeină"], 2),
                            (id_by_name["Orange Soda 0.5 L"], 1,
                             id_by_name["Apă carbogazoasă"], 1,
                             id_by_name["Zahăr"], 1,
                             id_by_name["Aromă portocale"], 1,
                             None, None,
                             None, None),
                            (id_by_name["Lemonade 0.5 L"], 1,
                             id_by_name["Apă carbogazoasă"], 1,
                             id_by_name["Zahăr"], 1,
                             id_by_name["Aromă lămâie"], 1,
                             None, None,
                             None, None),
                        ]
                        for (idf, qty,
                             m1, q1, m2, q2, m3, q3,
                             m4, q4, m5, q5) in recipes_rows:
                            self.cursor.execute("""
                                INSERT INTO recipes (id_final, quantity,
                                                     id_material1, quantity_material1,
                                                     id_material2, quantity_material2,
                                                     id_material3, quantity_material3,
                                                     id_material4, quantity_material4,
                                                     id_material5, quantity_material5)
                                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            """, (idf, qty,
                                  m1, q1, m2, q2, m3, q3,
                                  m4, q4, m5, q5))
                with self._dict_cur() as cur:
                    cur.execute("SELECT COUNT(*) AS cnt FROM orders")
                    if cur.fetchone()["cnt"] == 0:
                        # id client & angajat vânzări
                        cur.execute("SELECT id_customer FROM customers LIMIT 1")
                        r1 = cur.fetchone()
                        cust = r1["id_customer"] if r1 else None
                        cur.execute(
                            "SELECT id FROM employees "
                            "WHERE department='sales' LIMIT 1")
                        r2 = cur.fetchone()
                        emp = r2["id"] if r2 else None
                        now = datetime.utcnow()
                        self.cursor.execute("SELECT id_product,name,price FROM stock")
                        by_name = {r['name']: (r['id_product'], r['price'])
                                   for r in self.cursor.fetchall()}
                        order_items = [("Cola 0.5 L", 3), ("Orange Soda 0.5 L", 2)]
                        self.cursor.execute(
                            "INSERT INTO orders (id_client,data,progress,id_employee) "
                            "VALUES (%s,%s,'completed',%s) RETURNING id_order",
                            (cust, now, emp))
                        oid = self.cursor.fetchone()['id_order']
                        for name, qty in order_items:
                            pid, price = by_name.get(name, (None, None))
                            if pid is None or price is None:
                                continue
                            self.cursor.execute(
                                "INSERT INTO order_content "
                                "(id_order, id_product, quantity, price) "
                                "VALUES (%s,%s,%s,%s)",
                                (oid, pid, qty, price))
            self.connection.commit()
        except Exception as exc:
            import traceback, sys
            traceback.print_exc(file=sys.stderr)
            self.connection.rollback()

    def get_partner_order(self, order_id, employee_id=None):
        # Comanda partenerului cu un anumit ID.
        sql = "SELECT * FROM partner_orders WHERE id_order=%s"
        params = [order_id]
        if employee_id is not None:
            sql += " AND id_employee=%s"
            params.append(employee_id)
        self.cursor.execute(sql, tuple(params))
        return self.cursor.fetchone()

    def get_partner_orders_by_partner(self, partner_id):
        # Comenzile partenerului cu un anumit ID.
        self.cursor.execute(
            "SELECT * FROM partner_orders "
            "WHERE id_partner=%s "
            "ORDER BY data DESC",
            (partner_id,)
        )
        return self.cursor.fetchall()

    def upsert_partner_prices(self, partner_id, price_list):
        # Actualizează prețurile partenerului pentru produsele din listă.
        with self.connection:
            for item in price_list:
                pid   = item["id_product"]
                price = item["price"]
                if price <= 0:
                    self.cursor.execute(
                        "DELETE FROM partner_products "
                        "WHERE id_stock=%s AND id_partner=%s",
                        (pid, partner_id)
                    )
                    continue
                self.cursor.execute(
                    "UPDATE partner_products "
                    "SET price=%s "
                    "WHERE id_stock=%s AND id_partner=%s",
                    (price, pid, partner_id)
                )
                if self.cursor.rowcount == 0:
                    self.cursor.execute(
                        "INSERT INTO partner_products "
                        "  (id_stock, price, quantity, id_partner) "
                        "VALUES (%s,%s,0,%s)",
                        (pid, price, partner_id)
                    )
        return {"success": True}

    def produce_product(self, recipe_id, quantity):
        # Produce un produs pe baza rețetei.
        if quantity <= 0:
            return {"error": "Invalid quantity"}
        self.cursor.execute("""
            SELECT r.*, s.name, s.price, s.description, s.type
            FROM recipes r
            JOIN stock  s ON s.id_product = r.id_final
            WHERE r.id_final = %s
        """, (recipe_id,))
        recipe = self.cursor.fetchone()
        if not recipe:
            return {"error": "Recipe not found"}
        try:
            with self.connection:
                for i in range(1, 6):
                    mat_id = recipe.get(f"id_material{i}")
                    mat_qty = recipe.get(f"quantity_material{i}")
                    if mat_id and mat_qty:
                        need = mat_qty * quantity
                        have = None
                        with self._dict_cur() as qc:
                            qc.execute(
                                "SELECT quantity FROM stock WHERE id_product=%s",
                                (mat_id,))
                            row = qc.fetchone()
                            have = row["quantity"] if row else None
                        if have is None or have < need:
                            raise ValueError("Insufficient stock for material")
                        self.cursor.execute(
                            "UPDATE stock SET quantity = quantity - %s "
                            "WHERE id_product = %s",
                            (need, mat_id))
                added_qty = quantity * recipe["quantity"]
                self.cursor.execute(
                    "UPDATE stock SET quantity = quantity + %s "
                    "WHERE id_product = %s",
                    (added_qty, recipe_id)
                )
                if self.cursor.rowcount == 0:
                    self.cursor.execute(
                        """
                        INSERT INTO stock
                          (id_product, name, price, description, quantity, type)
                        VALUES (%s,%s,%s,%s,%s,%s)
                        """,
                        (
                            recipe_id,
                            recipe["name"],
                            recipe["price"],
                            recipe["description"],
                            added_qty,
                            recipe["type"]
                        )
                    )
            self.connection.commit()
            return {"success": True}
        except Exception as exc:
            self.connection.rollback()
            return {"error": str(exc)}

    def get_employee_id(self, username):
        # id-ul angajatului cu un anumit username.
        with self._dict_cur() as cur:
            cur.execute(
                "SELECT id FROM employees WHERE LOWER(username)=LOWER(%s)",
                (username,))
            row = cur.fetchone()
            return row['id'] if row else None

    def get_orders_by_employee(self, emp_id):
        # Comenzile unui angajat dat.
        self.cursor.execute(
            "SELECT * FROM orders "
            "WHERE id_employee=%s "
            "ORDER BY data DESC",
            (emp_id,)
        )
        return self.cursor.fetchall()

    def get_order_items(self, order_id):
        # Articolele dintr-o comandă dată.
        self.cursor.execute(
            """
            SELECT s.name, oc.quantity, oc.price
            FROM order_content oc
            JOIN stock s ON s.id_product = oc.id_product
            WHERE oc.id_order = %s
            """,
            (order_id,)
        )
        return self.cursor.fetchall()

    def update_order_status(self, emp_username, order_id, status):
        # Actualizează statusul unei comenzi.
        emp_id = self.get_employee_id(emp_username)
        if emp_id is None:
            return {"error": "Angajat inexistent"}
        self.cursor.execute(
            "UPDATE orders SET progress=%s "
            "WHERE id_order=%s AND id_employee=%s",
            (status, order_id, emp_id)
        )
        if self.cursor.rowcount == 0:
            self.connection.rollback()
            return {"error": "Comanda inexistentă sau nu vă aparține"}
        self.connection.commit()
        return {"success": True}

    def add_recipe(self, final_name, ingredients):
        # Adaugă o rețetă în baza de date.
        with self._dict_cur() as cur:
            cur.execute(
                "SELECT id_product FROM stock "
                "WHERE LOWER(name)=LOWER(%s) AND type='final'",
                (final_name,))
            r = cur.fetchone()
            id_final = r['id_product'] if r else None
        if id_final is None:
            return {"error": "Produs final inexistent în stock"}
        if not ingredients or len(ingredients) > 5:
            return {"error": "Ingrediente trebuie 1-5 articole"}
        mats: list[tuple[int, int]] = []
        for item in ingredients:
            nm = item.get("name", "").strip()
            qty = item.get("quantity", 0)
            if not nm or qty < 1:
                return {"error": f"Ingredient invalid: {item}"}
            with self._dict_cur() as _c:
                _c.execute(
                    "SELECT id_product FROM stock "
                    "WHERE LOWER(name)=LOWER(%s) AND type<>'final'",
                    (nm,))
                _r = _c.fetchone()
                mid = _r['id_product'] if _r else None
            if mid is None:
                return {"error": f"Materie primă inexistentă: {nm}"}
            mats.append((mid, qty))
        while len(mats) < 5:
            mats.append((None, None))
        try:
            with self.connection:
                self.cursor.execute("""
                    INSERT INTO recipes (
                        id_final, quantity,
                        id_material1, quantity_material1,
                        id_material2, quantity_material2,
                        id_material3, quantity_material3,
                        id_material4, quantity_material4,
                        id_material5, quantity_material5
                    ) VALUES (%s,1,
                              %s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    id_final,
                    *sum(([mid, qty] for mid, qty in mats), [])
                ))
            self.connection.commit()
            return {"success": True}
        except Exception as exc:
            self.connection.rollback()
            return {"error": str(exc)}

    def create_procurement_orders(self, employee_id, items):
        # Comenzile de achiziție pentru parteneri.
        if not items:
            return {"error": "Empty item list"}
        if employee_id is None:
            return {"error": "Invalid employee"}
        parts: dict[int, list[tuple[int, int, float]]] = {}
        try:
            with self._dict_cur() as cur:
                for sid, qty in items:
                    if qty <= 0:
                        return {"error": f"Invalid qty for product {sid}"}
                    cur.execute(
                        """
                        SELECT id_product, id_partner, price, quantity
                        FROM partner_products
                        WHERE id_stock=%s
                        ORDER BY price ASC
                        LIMIT 1
                        """,
                        (sid,))
                    row = cur.fetchone()
                    if not row:
                        return {"error": f"No supplier for product {sid}"}
                    if row["quantity"] < qty:
                        return {"error": f"Insufficient supplier stock for {sid}"}
                    parts.setdefault(row["id_partner"], []).append(
                        (row["id_product"], qty, row["price"])
                    )
        except Exception as exc:
            return {"error": str(exc)}
        try:
            with self.connection:
                created = []
                now = datetime.utcnow()
                for partner_id, lst in parts.items():
                    self.cursor.execute(
                        """
                        INSERT INTO partner_orders
                          (id_partner, data, status, id_employee)
                        VALUES (%s,%s,'pending',%s)
                        RETURNING id_order
                        """,
                        (partner_id, now, employee_id))
                    oid = self.cursor.fetchone()["id_order"]
                    self.cursor.executemany(
                        """
                        INSERT INTO partner_order_content
                          (id_product, id_order, quantity, price)
                        VALUES (%s,%s,%s,%s)
                        """,
                        [(ppid, oid, qty, price) for ppid, qty, price in lst]
                    )
                    created.append(oid)
            return {"success": True, "orders": created}
        except Exception as exc:
            self.connection.rollback()
            return {"error": str(exc)}

    def get_partner_order_items(self, order_id):
        # Articolele dintr-o comandă către partener.
        self.cursor.execute(
            """
            SELECT s.name, poc.quantity, poc.price
            FROM partner_order_content poc
            JOIN partner_products pp ON pp.id_product = poc.id_product
            JOIN stock s            ON s.id_product = pp.id_stock
            WHERE poc.id_order = %s
            """,
            (order_id,))
        return self.cursor.fetchall()

    def update_partner_order_status(self, partner_id, order_id, status):
        # Actualizează statusul unei comenzi către partener.
        self.cursor.execute(
            """
            UPDATE partner_orders
            SET status=%s
            WHERE id_order=%s AND id_partner=%s
            """,
            (status, order_id, partner_id)
        )
        if self.cursor.rowcount == 0:
            self.connection.rollback()
            return {"error": "Comandă inexistentă sau nu vă aparține"}
        self.connection.commit()
        return {"success": True}

    def place_order(self, customer_id, items):
        # Plasează o comandă pentru un client dat.
        if not customer_id:
            return {"error": "Client invalid"}
        if not items:
            return {"error": "Lista de produse este goală"}
        try:
            clean_items = [
                (int(pid), int(qty))
                for pid, qty in items
                if int(qty) > 0
            ]
        except Exception:
            return {"error": "Date produse invalide"}
        if not clean_items:
            return {"error": "Cantități invalide"}
        emp_id = None
        with self._dict_cur() as cur:
            cur.execute(
                "SELECT id FROM employees WHERE department='sales' "
                "ORDER BY id LIMIT 1")
            row = cur.fetchone()
            emp_id = row["id"] if row else None
        if emp_id is None:
            return {"error": "Nu există angajați vânzări"}
        try:
            from datetime import datetime
            now = datetime.utcnow()
            with self.connection:
                self.cursor.execute(
                    "INSERT INTO orders (id_client,data,progress,id_employee) "
                    "VALUES (%s,%s,'pending',%s) RETURNING id_order",
                    (customer_id, now, emp_id)
                )
                oid = self.cursor.fetchone()["id_order"]
                for pid, qty in clean_items:
                    price = None
                    with self._dict_cur() as pcur:
                        pcur.execute("SELECT price FROM stock WHERE id_product=%s",
                                     (pid,))
                        prow = pcur.fetchone()
                        price = prow["price"] if prow else None
                    if price is None:
                        raise ValueError(f"Produs inexistent ID {pid}")
                    self.cursor.execute(
                        "INSERT INTO order_content "
                        "(id_order,id_product,quantity,price) "
                        "VALUES (%s,%s,%s,%s)",
                        (oid, pid, qty, price)
                    )
            self.connection.commit()
            return {"success": True, "order_id": oid}
        except Exception as exc:
            self.connection.rollback()
            return {"error": str(exc)}
