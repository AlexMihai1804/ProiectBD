from flask import Flask
from db import Database
app = Flask(__name__)
database = Database()

@app.route('/')
def hello_world():  # put application's code here
    return 'Hello World!'


if __name__ == '__main__':
    app.run()
