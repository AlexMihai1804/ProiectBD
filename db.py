import sqlite3

class Database:
    def __init__(self):
        self.connection = sqlite3.connect('data.db')
        self.cursor = self.connection.cursor()
        self.create_table()
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
                `usename` TEXT NOT NULL,
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
    def get_users(self):
        self.cursor.execute('SELECT * FROM employees')
        return self.cursor.fetchall()
