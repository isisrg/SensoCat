from flask import render_template, flash, redirect, request
from app import app
from app.forms import LoginForm, UploadForm, NewStationForm

from distutils.file_util import move_file
import boto3
from datetime import datetime
from pprint import pprint
from botocore.exceptions import ClientError
import json
import pandas as pd
import numpy as np

from decimal import Decimal

dynamodb = boto3.resource('dynamodb')
stations_table = dynamodb.Table('Estaciones')

#DECORATORS
@app.route('/')
@app.route('/home')
def home():
    #Returns all of the table's data
    table_data = stations_table.scan()
    #Returns the items from the data collected and saves it into pandas
    items_data = pd.DataFrame(table_data['Items'])
    #print(items_data)
    items_data=items_data.values.tolist()
    return render_template('home.html', title='Home', items_data=json.dumps(items_data))

@app.route('/home/modal')
def modal():
    #Returns all of the table's data
    table_data = stations_table.scan()
    #Returns the items from the data collected and saves it into pandas
    items_data = pd.DataFrame(table_data['Items'])
    #print(items_data)
    items_data=items_data.values.tolist()
    return render_template('modal.html', title='Home', items_data=json.dumps(items_data))

@app.route('/about')
def about():
    return render_template('about.html', title='Sobre nosotros')

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    form = UploadForm()
    if form.validate_on_submit():
        return redirect('/upload')

    if request.method == 'POST':
        data_type = form.data_type.data
        locations_csv = form.file.data
        df = pd.read_csv(locations_csv, delimiter=';')
        if data_type == 'stations':
            #df.insert(0, 'Id', np.arange(start=1, stop=len(df)+1, step=1))
            table = 'Estaciones'
            mode = 1
        if data_type == 'reports':
            table = 'Informes'
            mode = 2

        #Header values
        header = df.columns.values
        #Number of rows of the csv
        row_size = df.shape[0]
        #Number of columns of the csv
        col_size = df.shape[1]

        for count_row in range(0, row_size):
            for count_col in range(0, col_size):
                row_values = df.iloc[count_row,:].values
                #If the data is from a captor the date format is changed taking the seconds out
                if str(header[count_col]) == 'Timestamp' and mode == 1:
                    old_date = str(row_values[count_col])
                    date = datetime.strptime(f'{old_date}', '%d/%m/%Y %H:%M:%S')
                    new_date = date.strftime('%d/%m/%Y %H:%M')
                    row_values[count_col] = str(new_date)
                
                #If the data is from a reference station the date format is changed so it stays with the same format as the date in the captors
                if str(header[count_col]) == 'Timestamp' and mode == 2:
                    old_date = str(row_values[count_col])
                    date = datetime.strptime(f'{old_date}', '%Y-%m-%dT%H:%M')
                    new_date = date.strftime('%d/%m/%Y %H:%M')
                    row_values[count_col] = str(new_date)
                
                if count_col == 0:
                    data_json = '{"' + str(header[count_col]) + '": "' + str(row_values[count_col]) + '"'     
                else:
                    data_json += ', "' + str(header[count_col]) + '": "' + str(row_values[count_col]) + '"'

            data_json += '}'
            #Data converted to JSON format
            converted_data = json.loads(data_json)
            dynamodb = boto3.resource('dynamodb')
            #Indicates which table is going to be used
            selected_table = dynamodb.Table(table)
            selected_table.put_item(Item=converted_data)

    return render_template('upload.html', title='Subir archivo', form=form)

@app.route('/new_station', methods=['GET', 'POST'])
def new_station():
    form_new_station = NewStationForm()
    if form_new_station.validate_on_submit():
        if request.method == 'POST':
            return render_template('submit_station.html', title='Nueva estación', form_new_station=form_new_station)
    return render_template('new_station.html', title='Nueva estación', form_new_station=form_new_station)

@app.route('/submit_station', methods=['GET', 'POST'])
def submit_station():
    form_new_station = NewStationForm()

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('Estaciones')
    #Returns all of the table's data
    table_data = table.scan()
    #Returns the items from the data collected and saves it into pandas
    items_data = pd.DataFrame(table_data['Items'])

    #Header values
    header = items_data.columns.values
    #Number of rows of the csv
    row_size = items_data.shape[0]
    #Number of columns of the csv
    col_size = items_data.shape[1]

    #Primero equals 0 if its the first iteration on the Contaminantes column (also indicates wether the Contaminantes column exists or not)
    primero = 0

    for count_col in range(0, col_size):  
        if header[count_col] == 'Longitud': data = form_new_station.longitude.data
        if header[count_col] == 'Latitud': data = form_new_station.latitude.data
        if header[count_col] == 'Nombre': data = form_new_station.name.data
        if header[count_col] == 'Contaminantes': data = form_new_station.pollutants.data

        if count_col == 0:
            data_json = '{"' + str(header[count_col]) + '": "' + str(data) + '"'      
        else:
            if header[count_col] == 'Contaminantes':
                data_json += ', "' + str(header[count_col]) + '": ['
                for nested in form_new_station.pollutants.entries:
                    if primero == 0:
                        data_json += '"' + str(nested.data) + '"'
                        primero = 1
                    else:
                        data_json += ', "' + str(nested.data) + '"'
                data_json += ']'
            else:
                data_json += ', "' + str(header[count_col]) + '": "' + str(data) + '"'

    #If Contaminantes column does not exists then creates one with the data specified by the user in the form
    if primero == 0:
        data_json += ', "Contaminantes": ['
        for nested in form_new_station.pollutants.entries:
            if primero == 0:
                data_json += '"' + str(nested.data) + '"'
                primero = 1
            else:
                data_json += ', "' + str(nested.data) + '"'
        data_json += ']'

    #print(str(form_new_station.pollutants.data))
    #print(len(form_new_station.pollutants.data))

    data_json += '}'
    print(data_json)
    #Data converted to JSON format
    converted_data = json.loads(data_json)
    dynamodb = boto3.resource('dynamodb')
    #Indicates which table is going to be used
    selected_table = dynamodb.Table('Estaciones')
    selected_table.put_item(Item=converted_data)
    return render_template('submit_station.html', title='Estación', form_new_station=form_new_station)
