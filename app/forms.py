from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, FileField, RadioField, FieldList, FormField
from wtforms.validators import DataRequired
from flask_wtf.file import FileField, FileRequired, FileAllowed

class LoginForm(FlaskForm):
	#Validator argument is used to attach validation behaviours to fields
	#DataRequired validator checks that the field is not submitted empty
	username = StringField('Username', validators=[DataRequired()])
	password = PasswordField('Password', validators=[DataRequired()])
	remember_me = BooleanField('Remember Me')
	submit = SubmitField('Sign In')

class UploadForm(FlaskForm):
	#Creates two radio buttons, one for stations and another one for reports. Forces the user to pick one of the two, if none of those are selected then appears a message to inform the user
	data_type = RadioField('data_type', choices=[('stations', 'Estaciones de referencia'), ('reports', 'Informes de estaciones de referencia')], validators=[DataRequired()])
	file = FileField('file', validators=[FileRequired(), FileAllowed(['csv'], 'Solo archivos CSV!')])

class NewStationForm(FlaskForm):
	name = StringField('Nombre', validators=[DataRequired()])
	latitude = StringField('Latitud', validators=[DataRequired()])
	longitude = StringField('Longitud', validators=[DataRequired()])
	pollutants = FieldList(StringField('Contaminante', validators=[DataRequired()]), min_entries=1, max_entries=5)

