import os

class Config(object):
	#Protect web forms against Cross-Site Request Forgery attack
	#The first term looks for the value of an environment variable, also called SECRET_KEY
	#The second term is a hardcoded string so if the environment does not define a variable, then the hardcoded string is udes instead as a default
	SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'