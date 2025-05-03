import sqlite3

class Database:
    def __init__(self):
        self.connection = sqlite3.connect('data.db')
        self.cursor = self.connection.cursor()
        self.create_table()
    def create_table(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        self.connection.commit()
    def get_users(self):
        self.cursor.execute('SELECT * FROM users')
        return self.cursor.fetchall()