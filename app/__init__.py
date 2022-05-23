#Creates the application object as an instance of class Flask imported from the flask package
from flask import Flask
from config import Config

#Variable name -> set to the name of the module in which it is used
app = Flask(__name__)
#Read and apply the config file
app.config.from_object(Config)

#Bottom import of routes is a workaround to circular imports
#ROUTES -> differents URLs that the application implements
from app import routes