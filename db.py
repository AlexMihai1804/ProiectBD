import sqlite3
from datetime import datetime


class Database:
    def __init__(self):
        self.connection = sqlite3.connect('data.db', check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.cursor = self.connection.cursor()
        self.create_table()
        self.create_triggers()

    def create_table(self):
        self.cursor.executescript('''
            CREATE TABLE IF NOT EXISTS `employees` (
                `id` integer primary key NOT NULL UNIQUE,
                `name` TEXT NOT NULL,
                `surname` TEXT NOT NULL,
                `department` TEXT NOT NULL,
                `salary` REAL NOT NULL,
                `email` TEXT NOT NULL,
                `phone_number` REAL NOT NULL,
                `adress` TEXT NOT NULL,
                `username` TEXT NOT NULL,
                `password` TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS `customers` (
                `id_customer` integer primary key NOT NULL UNIQUE,
                `name` TEXT NOT NULL,
                `surname` TEXT NOT NULL,
                `username` TEXT NOT NULL,
                `password` TEXT NOT NULL,
                `email` TEXT NOT NULL,
                `address` TEXT NOT NULL DEFAULT 'null',
                `phone_number` REAL NOT NULL DEFAULT 'null'
            );
            CREATE TABLE IF NOT EXISTS `stock` (
                `id_product` integer primary key NOT NULL UNIQUE,
                `name` TEXT NOT NULL,
                `price` REAL NOT NULL,
                `description` TEXT NOT NULL,
                `quantity` INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS `order_content` (
                `id_item` integer primary key NOT NULL UNIQUE,
                `id_order` INTEGER NOT NULL,
                `id_product` INTEGER NOT NULL,
                `quantity` INTEGER NOT NULL,
                `price` REAL NOT NULL,
            FOREIGN KEY(`id_order`) REFERENCES `orders`(`id_order`),
            FOREIGN KEY(`id_product`) REFERENCES `stock`(`id_product`)
            );
            CREATE TABLE IF NOT EXISTS `recipes` (
                `id_recipe` integer primary key NOT NULL UNIQUE,
                `id_final` INTEGER NOT NULL,
                `quantitiy` INTEGER NOT NULL,
                `id_material1` INTEGER NOT NULL,
                `quantity_material1` INTEGER NOT NULL,
                `id_material2` INTEGER DEFAULT 'null',
                `quantity_material2` INTEGER DEFAULT 'null',
                `id_material3` INTEGER DEFAULT 'null',
                `quantity_material3` INTEGER DEFAULT 'null',
                `id_material4` INTEGER DEFAULT 'null',
                `quantity_material4` INTEGER DEFAULT 'null',
                `id_material5` INTEGER DEFAULT 'null',
                `quantity_material5` INTEGER DEFAULT 'null',
            FOREIGN KEY(`id_final`) REFERENCES `stock`(`id_product`),
            FOREIGN KEY(`id_material1`) REFERENCES `stock`(`id_product`),
            FOREIGN KEY(`id_material2`) REFERENCES `stock`(`id_product`),
            FOREIGN KEY(`id_material3`) REFERENCES `stock`(`id_product`),
            FOREIGN KEY(`id_material4`) REFERENCES `stock`(`id_product`),
            FOREIGN KEY(`id_material5`) REFERENCES `stock`(`id_product`)
            );
            CREATE TABLE IF NOT EXISTS `partner_orders` (
                `id_order` integer primary key NOT NULL UNIQUE,
                `id_partner` INTEGER NOT NULL,
                `data` REAL NOT NULL,
                `status` TEXT NOT NULL,
                `id_employee` INTEGER NOT NULL,
            FOREIGN KEY(`id_employee`) REFERENCES `employees`(`id`)
            );
            CREATE TABLE IF NOT EXISTS `partner_order_content` (
                `id_product` INTEGER NOT NULL,
                `id` integer primary key NOT NULL UNIQUE,
                `id_order` INTEGER NOT NULL,
                `quantity` INTEGER NOT NULL,
                `price` REAL NOT NULL,
            FOREIGN KEY(`id_product`) REFERENCES `partner_products`(`id_product`),
            FOREIGN KEY(`id_order`) REFERENCES `partner_orders`(`id_order`)
            );
            CREATE TABLE IF NOT EXISTS `orders` (
                `id_order` integer primary key NOT NULL UNIQUE,
                `id_client` INTEGER NOT NULL,
                `data` REAL NOT NULL,
                `progress` TEXT NOT NULL,
                `id_employee` INTEGER NOT NULL,
            FOREIGN KEY(`id_client`) REFERENCES `customers`(`id_customer`),
            FOREIGN KEY(`id_employee`) REFERENCES `employees`(`id`)
            );
            CREATE TABLE IF NOT EXISTS `partners` (
                `id_partner` integer primary key NOT NULL UNIQUE,
                `name` INTEGER NOT NULL,
                `username` TEXT NOT NULL,
                `password` TEXT NOT NULL,
                `address` TEXT,
                `phone_number` REAL,
                `email` TEXT
            );
            CREATE TABLE IF NOT EXISTS `partner_products` (
                `id_product` integer primary key NOT NULL UNIQUE,
                `id_stock` INTEGER NOT NULL,
                `price` REAL NOT NULL,
                `id_partner` INTEGER NOT NULL,
            FOREIGN KEY(`id_stock`) REFERENCES `stock`(`id_product`),
            FOREIGN KEY(`id_partner`) REFERENCES `partners`(`id_partner`)
);
        ''')
        self.connection.commit()

    def create_triggers(self):
        self.cursor.executescript('''
            CREATE TRIGGER IF NOT EXISTS trg_before_insert_order_content
            BEFORE INSERT ON order_content
            FOR EACH ROW
            BEGIN
                SELECT CASE WHEN (SELECT quantity FROM stock WHERE id_product=NEW.id_product)<NEW.quantity THEN RAISE(ROLLBACK,'Insufficient stock') END;
                UPDATE stock SET quantity=quantity-NEW.quantity WHERE id_product=NEW.id_product;
            END;
            CREATE TRIGGER IF NOT EXISTS trg_before_update_order_content
            BEFORE UPDATE OF quantity ON order_content
            FOR EACH ROW
            BEGIN
                SELECT CASE WHEN NEW.quantity>OLD.quantity AND (SELECT quantity FROM stock WHERE id_product=NEW.id_product)<(NEW.quantity-OLD.quantity) THEN RAISE(ROLLBACK,'Insufficient stock') END;
                UPDATE stock SET quantity=quantity-(NEW.quantity-OLD.quantity) WHERE id_product=NEW.id_product;
            END;
            CREATE TRIGGER IF NOT EXISTS trg_before_delete_order_content
            BEFORE DELETE ON order_content
            FOR EACH ROW
            BEGIN
                UPDATE stock SET quantity=quantity+OLD.quantity WHERE id_product=OLD.id_product;
            END;
            CREATE TRIGGER IF NOT EXISTS trg_before_insert_partner_order_content
            BEFORE INSERT ON partner_order_content
            FOR EACH ROW
            BEGIN
                SELECT CASE WHEN (SELECT quantity FROM partner_products WHERE id_product=NEW.id_product)<NEW.quantity THEN RAISE(ROLLBACK,'Insufficient stock') END;
                UPDATE partner_products SET quantity=quantity-NEW.quantity WHERE id_product=NEW.id_product;
            END;
            CREATE TRIGGER IF NOT EXISTS trg_before_update_partner_order_content
            BEFORE UPDATE OF quantity ON partner_order_content
            FOR EACH ROW
            BEGIN
                SELECT CASE WHEN NEW.quantity>OLD.quantity AND (SELECT quantity FROM partner_products WHERE id_product=NEW.id_product)<(NEW.quantity-OLD.quantity) THEN RAISE(ROLLBACK,'Insufficient stock') END;
                UPDATE partner_products SET quantity=quantity-(NEW.quantity-OLD.quantity) WHERE id_product=NEW.id_product;
            END;
            CREATE TRIGGER IF NOT EXISTS trg_before_delete_partner_order_content
            BEFORE DELETE ON partner_order_content
            FOR EACH ROW
            BEGIN
                UPDATE partner_products SET quantity=quantity+OLD.quantity WHERE id_product=OLD.id_product;
            END;
        ''')
        self.connection.commit()

    def get_employees(self):
        self.cursor.execute('SELECT * FROM employees')
        return self.cursor.fetchall()

    def verify_customer(self, username, password):
        self.cursor.execute('SELECT * FROM customers WHERE username=? AND password=?', (username, password))
        result = self.cursor.fetchone()
        if result:
            return True
        else:
            return False

    def verify_employee(self, username, password):
        self.cursor.execute('SELECT * FROM employees WHERE username=? AND password=?', (username, password))
        result = self.cursor.fetchone()
        if result:
            return True
        else:
            return False

    def verify_partner(self, username, password):
        self.cursor.execute('SELECT * FROM partners WHERE username=? AND password=?', (username, password))
        result = self.cursor.fetchone()
        if result:
            return True
        else:
            return False

    def get_customers(self):
        self.cursor.execute('SELECT * FROM customers')
        return self.cursor.fetchall()

    def get_orders(self):
        self.cursor.execute('SELECT * FROM orders')
        return self.cursor.fetchall()

    def get_order_content(self):
        self.cursor.execute('SELECT * FROM order_content')
        return self.cursor.fetchall()

    def get_stock(self):
        self.cursor.execute('SELECT * FROM stock')
        return self.cursor.fetchall()

    def get_partners(self):
        self.cursor.execute('SELECT * FROM partners')
        return self.cursor.fetchall()

    def get_partner_products(self):
        self.cursor.execute('SELECT * FROM partner_products')
        return self.cursor.fetchall()

    def get_partner_orders(self):
        self.cursor.execute('SELECT * FROM partner_orders')
        return self.cursor.fetchall()

    def get_partner_order_content(self):
        self.cursor.execute('SELECT * FROM partner_order_content')
        return self.cursor.fetchall()

    def get_recipes(self):
        self.cursor.execute('SELECT * FROM recipes')
        return self.cursor.fetchall()

    def get_order_quantity(self, order_id):
        self.cursor.execute('SELECT quantity FROM order_content WHERE id_order = ?', (order_id,))
        result = self.cursor.fetchone()
        return result[0] if result else 0
    
    def get_partner_order_quantity(self, order_id):
        self.cursor.execute('SELECT quantity FROM partnet_order_content WHERE id_order = ?', (order_id,))
        result = self.cursor.fetchone()
        return result[0] if result else 0 
    
    def get_least_busy_employee(self, department):
        self.cursor.execute("""
            SELECT e.id
            FROM employees e
            LEFT JOIN orders o
              ON o.id_employee = e.id
             AND o.progress != 'completed'
            WHERE e.department IN (?)
            GROUP BY e.id
            ORDER BY COUNT(o.id_order) ASC
            LIMIT 1
        """, (department,))
        row = self.cursor.fetchone()
        return row[0] if row else None

    def place_order(self, customer_id, item_list):
        if not item_list:
            return {'error': 'Empty item list'}
        employee_id = self.get_least_busy_employee('sales')
        if not employee_id:
            return {'error': 'No available employee'}
        with self.connection:
            now = datetime.utcnow().isoformat(' ')
            self.cursor.execute(
                'INSERT INTO orders(id_client,data,progress,id_employee) VALUES(?,?,?,?)',
                (customer_id, now, 'pending', employee_id)
            )
            order_id = self.cursor.lastrowid
            for pid, qty in item_list:
                if qty <= 0:
                    return {'error': 'Invalid quantity'}
                row = self.cursor.execute(
                    'SELECT price FROM stock WHERE id_product=?', (pid,)
                ).fetchone()
                if not row:
                    return {'error': 'Product not found'}
                price = row['price']
                self.cursor.execute(
                    'INSERT INTO order_content(id_order,id_product,quantity,price) VALUES(?,?,?,?)',
                    (order_id, pid, qty, price)
                )
        return {'success': True, 'order_id': order_id}

    def place_partner_order(self, partner_id, item_list):
        if not item_list:
            return {'error': 'Empty item list'}
        employee_id = self.get_least_busy_employee('sales')
        if not employee_id:
            return {'error': 'No available employee'}
        with self.connection:
            now = datetime.utcnow().isoformat(' ')
            self.cursor.execute(
                'INSERT INTO partner_orders(id_partner,data,status,id_employee) VALUES(?,?,?,?)',
                (partner_id, now, 'pending', employee_id)
            )
            order_id = self.cursor.lastrowid
            for pid, qty in item_list:
                if qty <= 0:
                    return {'error': 'Invalid quantity'}
                row = self.cursor.execute(
                    'SELECT price FROM partner_products WHERE id_product=?', (pid,)
                ).fetchone()
                if not row:
                    return {'error': 'Product not found'}
                price = row['price']
                self.cursor.execute(
                    'INSERT INTO partner_order_content(id_product,id_order,quantity,price) VALUES(?,?,?,?)',
                    (pid, order_id, qty, price)
                )
        return {'success': True, 'order_id': order_id}

    def reset_customer_password(self, username, new_password):
        self.cursor.execute('SELECT * FROM customers WHERE username = ?', (username,))
        if not self.cursor.fetchone():
            return {'error' : 'User not found'}
    
        self.cursor.execute('UPDATE customers SET password = ? WHERE username = ?', (new_password, username))
        self.connection.commit()
        return {'succes': True}
    
    def reset_employee_password(self, username, new_password):
        self.cursor.execute('SELECT * FROM employees WHERE username = ?', (username,))
        if not self.cursor.fetchone():
            return {'error' : 'User not found'}
    
        self.cursor.execute('UPDATE employees SET password = ? WHERE username = ?', (new_password, username))
        self.connection.commit()
        return {'succes': True}
    
    def search_product_by_name(self, name):
        query = "SELECT * FROM products WHERE LOWER(name) LIKE ?"
        self.cursor.execute(query, ('%' + name.lower() + '%'))
        return self.cursor.fetchall()
    
    def get_orders_by_customer(self, customer_id):
        query = "SELECT * FROM orders WHERE customer_id = ?"
        self.cursor.execute(query, (customer_id,))
        return self.cursor.fetchall()
    
    def get_orders_by_status(self, status):
        query = "SELECT * FROM orders WHERE status = ?"
        self.cursor.execute(query, (status,))
        return self.cursor.fetchall()