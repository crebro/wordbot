from flask import Flask
from threading import Thread
import os

app = Flask(__name__)

@app.route('/')
def index():
    return "Alive"

def run():
  app.run(host='0.0.0.0',port=os.environ['PORT'])

def keep_alive():  
    t = Thread(target=run)
    t.start()