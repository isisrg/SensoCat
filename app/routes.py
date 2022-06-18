#Creates the application object as an instance of class Flask imported from the flask package
from crypt import methods
from email import message
from sqlite3 import Timestamp
from weakref import finalize
from flask import Flask

# FLASK
from flask import render_template, redirect, request
#APP
from app import app
from app.forms import UploadForm, NewStationForm
#BOTO3
import boto3
from boto3.dynamodb.conditions import Key
import botocore
from botocore.exceptions import ClientError
#UTILITIES
from flask_bootstrap import Bootstrap
import pandas as pd
import numpy as np
import json
from datetime import datetime


# from itertools import count
# from turtle import circle
# from typing import final
# from distutils.file_util import move_file

#DYNAMODB connection and tables
dynamodb = boto3.resource('dynamodb')
stations_table = dynamodb.Table('Estaciones')
reports_table = dynamodb.Table('Informes')

Bootstrap(app)

#DECORATORS
@app.route('/')

@app.route('/home')
def home():
    #Returns all of the table's data
    table_data = stations_table.scan()
    #Returns the items from the data collected and saves it into pandas
    items_data = pd.DataFrame(table_data['Items'])

    #Header values
    header = items_data.columns.values
    header = header.tolist()
    name_index = header.index('Nombre')
    latitude_index = header.index('Latitud')
    longitude_index = header.index('Longitud')
    #Number of rows of the csv
    row_size = items_data.shape[0]

    for count_row in range(0, row_size):
        station_name = items_data.iloc[count_row,:].values[name_index]
        initial_date = reports_table.query(
            Limit = 1,
            # TRUE -> sort order is ascending
            ScanIndexForward = True,
            KeyConditionExpression=Key('Nombre').eq(station_name)
        )
        initial_date = initial_date['Items']

        final_date = reports_table.query(
            Limit = 1,
            # TRUE -> sort order is descending
            ScanIndexForward = False,
            KeyConditionExpression=Key('Nombre').eq(station_name)
        )
        final_date = final_date['Items']
        
        if initial_date and final_date:
            initial_date = initial_date[0]['Timestamp']
            final_date = final_date[0]['Timestamp']
            print('Station: ', station_name, ' Initial date: ', initial_date, ' Final date: ', final_date)

            last_readings = reports_table.query(
            Limit = 1,
            KeyConditionExpression=Key('Nombre').eq(station_name) & Key('Timestamp').eq(final_date)
            )
            last_readings = last_readings['Items'][0]
            last_readings = dict(last_readings)
            first_sensor = 0

            for key, value in last_readings.items():
                if key != 'Nombre' and key != 'Timestamp':
                    if first_sensor == 0: 
                        data_json = str(key) + ':' + str(value) 
                        first_sensor = 1    
                    else:
                        data_json += ',' + str(key) + ':' + str(value)
                        
        else:
            initial_date = "nan"
            final_date = "nan"
            data_json = "nan"

        stations_table.update_item(
            Key={'Nombre': str(station_name)},
            UpdateExpression="SET #fechainicio = :idate, #fechafin = :fdate",
            ExpressionAttributeNames={
                "#fechainicio": "Fecha-inicio",
                "#fechafin": "Fecha-fin"
            },
            ExpressionAttributeValues={
                ':idate': str(initial_date),
                ':fdate': str(final_date)
            },
            ReturnValues="UPDATED_NEW"
        )
        
        stations_table.update_item(
            Key={'Nombre': str(station_name)},
            UpdateExpression="SET #ultimalectura = :ulectura",
            ExpressionAttributeNames={
                "#ultimalectura": "Ultima-lectura"
            },
            ExpressionAttributeValues={
                ':ulectura': str(data_json),
            },
            ReturnValues="UPDATED_NEW"
        )
        print(station_name)
    items_data=items_data.values.tolist()
    return render_template('home.html', title='Inicio', items_data=json.dumps(items_data), name_index=name_index, latitude_index=latitude_index, longitude_index=longitude_index)

@app.route('/home/chart_table/<station_name>/<sensor>/<initial_date>/<final_date>', methods=['GET', 'POST'])
def chart_table(station_name, sensor, initial_date, final_date):
    if request.method == 'GET':
        reports = reports_table.query(
            KeyConditionExpression=Key('Nombre').eq(station_name) & Key('Timestamp').between(initial_date, final_date)
        )
        reports = reports['Items']
        labels = []
        data = []
        for report in reports:
            labels.append(report['Timestamp'].replace('T', ' '))
            data.append("{:.2f}".format(float(report[sensor])))
        initial_date = initial_date.replace('T', ' ')
        final_date = final_date.replace('T', ' ')

        return render_template('chart_table.html', title='Información', station_name=station_name, sensor=sensor, initial_date = initial_date, final_date = final_date, labels = labels, data = data)

    if request.method == 'POST':
        return redirect('/home')
        
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    form = UploadForm()
    if form.validate_on_submit():
        if request.method == 'POST':
            return render_template('submit_csv.html', title='Subir archivo', form=form)
    return render_template('upload.html', title='Subir archivo', form=form)

@app.route('/upload/submit_csv', methods=['GET', 'POST'])
def submit_csv():
    if request.method == 'GET':
        return redirect('/upload')

    if request.method == 'POST':
        form = UploadForm()
        data_type = form.data_type.data
        locations_csv = form.file.data
        file_name = locations_csv.filename.split('.')[0]
        df = pd.read_csv(locations_csv, delimiter=';')
        if data_type == 'stations':
            table = 'Estaciones'
            mode = 0

        if data_type == 'reports-captor':
            df.insert(0, 'Nombre', file_name)
            table = 'Informes'
            mode = 1

        if data_type == 'reports-ref':
            df.insert(0, 'Nombre', file_name)
            table = 'Informes'
            mode = 2

        #Header values
        header = df.columns.values
        #Number of rows of the csv
        row_size = df.shape[0]
        #Number of columns of the csv
        col_size = df.shape[1]
        #Index of the attribute 'Nombre'
        name_index = header.tolist()
        name_index = name_index.index('Nombre')

        dynamodb = boto3.resource('dynamodb')
        #Indicates which table is going to be used
        selected_table = dynamodb.Table(table)

        #operation_message indicates the status of the operation, being successful by default, and if some error happened it is changed to the error message
        # operation_message = 'Archivo subido correctamente'
        #operation_code is empty and not send to submit_csv.html unless an error happens, in that case operation_code will have the error code of the operation that has failed
        # operation_code = ''

        for count_row in range(0, row_size):
            #print to show the progression of the upload on the terminal
            print(count_row + 1, '/', row_size)
            station_name = df.iloc[count_row,:].values[name_index]
            # with table.batch_writer() as batch:
            for count_col in range(0, col_size):
                row_values = df.iloc[count_row,:].values
                    
                if str(header[count_col]) == 'date':        
                    header[count_col] = 'Timestamp'

                #If the data is from a captor the date format is changed taking the seconds out
                if str(header[count_col]) == 'Timestamp' and mode == 1:
                    #If the data is from one of the captor20xxx captors, which have the date with a different format from the captor170xx captors, is changed so it stays with the same format as all of the others
                    if 'captor20' in row_values[0]:
                        old_date = str(row_values[count_col])
                        date = datetime.strptime(f'{old_date}', '%Y-%m-%d %H:%M:%S')
                        new_date = date.strftime('%Y-%m-%dT%H:%M')
                        row_values[count_col] = str(new_date)

                    #All the captor170xx captors
                    elif 'captor170' in row_values[0]:
                        #If the data if from captor17013, captor17016 or captor17017, which have the date with a different format from all the other captors, including the captors from captor170xx, is changed so it stays with the same format as all of the others
                        if (row_values[0] == 'captor17013' or row_values[0] == 'captor17016' or row_values[0] =='captor17017'):
                            old_date = str(row_values[count_col])
                            date = datetime.strptime(f'{old_date}', '%d/%m/%Y %H:%M')
                            new_date = date.strftime('%Y-%m-%dT%H:%M')
                            row_values[count_col] = str(new_date)
                            
                        #If the data is from the rest of the captor170xx captors, the date format is changed so it stays with the same format as all of the others
                        else:
                            old_date = str(row_values[count_col])
                            date = datetime.strptime(f'{old_date}', '%d/%m/%Y %H:%M:%S')
                            new_date = date.strftime('%Y-%m-%dT%H:%M')
                            row_values[count_col] = str(new_date)
                
                #If the data is from a reference station the date format is changed so it stays with the same format as the date in the captors
                if str(header[count_col]) == 'Timestamp' and mode == 2:
                    old_date = str(row_values[count_col])
                    date = datetime.strptime(f'{old_date}', '%Y-%m-%dT%H:%M')
                    new_date = date.strftime('%Y-%m-%dT%H:%M')
                    row_values[count_col] = str(new_date)

                if count_col == 0: 
                    data_json = '{"' + str(header[count_col]) + '": "' + str(row_values[count_col]) + '"'     
                else:
                    data_json += ', "' + str(header[count_col]) + '": "' + str(row_values[count_col]) + '"'
                
            data_json += '}'
            #Data converted to JSON format
            converted_data = json.loads(data_json)
            selected_table.put_item(Item=converted_data)
            # try:
            #     response = selected_table.put_item(Item='a')
            # except botocore.exceptions.ClientError as error:
            #     operation_code = error.response['ClientError']['Error']['Code']
            #     operation_message = error.response['Error']['Message']
            #     return render_template('submit_csv.html', title='Subir archivo', operation_message=operation_message, operation_code=operation_code)
        # return render_template('submit_csv.html', title='Subir archivo', form=form, operation_message=operation_message)
        return render_template('submit_csv.html', title='Subir archivo', form=form)

@app.route('/new_station', methods=['GET', 'POST'])
def new_station():
    form_new_station = NewStationForm()
    if form_new_station.validate_on_submit():
        if request.method == 'POST':
            return render_template('submit_station.html', title='Nueva estación', form_new_station=form_new_station)
    return render_template('new_station.html', title='Nueva estación', form_new_station=form_new_station)

@app.route('/new_station/submit_station', methods=['GET', 'POST'])
def submit_station():

    if request.method == 'GET':
        return redirect('/new_station')
        
    if request.method == 'POST':
        form_new_station = NewStationForm()
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table('Estaciones')
        #Returns all of the table's data
        table_data = table.scan()
        #Returns the items from the data collected and saves it into pandas
        items_data = pd.DataFrame(table_data['Items'])

        #Header values
        header = items_data.columns.values
        print('header: ', header[0])
        #Header values
        header = header.tolist()

        #The data must follow the order specified in locations.csv [Nombre, Latitud, Longitud, Sensores, Fecha-inicio, Fecha-fin, Ultima-lectura],
        # if it does not follow this order then an error in the home.html will happen when trying to access data
        data_json='{"Nombre": "'+form_new_station.name.data+'", "Latitud": "'+form_new_station.latitude.data+'", "Longitud": "'+form_new_station.longitude.data+'", "Sensores": "'
        sensor_data = form_new_station.sensors.entries
        #first equals 0 if its the first iteration on the Sensores column (also indicates wether the Sensores column exists or not)
        first = 0
        for nested in sensor_data:
            if first == 0:
                data_json += str(nested.data)
                first = 1
            else:
                data_json += ','+str(nested.data)
        data_json += '", "Fecha-inicio": "nan", "Fecha-fin": "nan", "Ultima-lectura": "nan"}'

        converted_data = json.loads(data_json)
        dynamodb = boto3.resource('dynamodb')
        #Indicates which table is going to be used
        selected_table = dynamodb.Table('Estaciones')
        selected_table.put_item(Item=converted_data)
        return render_template('submit_station.html', title='Estación', form_new_station=form_new_station)

@app.route('/about')
def about():
    return render_template('about.html', title='Sobre nosotros')

@app.route('/index')
def index():
    dynamodb = boto3.resource('dynamodb')
    #Create the DynamoDB table
    table = dynamodb.create_table(
        TableName='Informes',
        KeySchema=[
            {
                'AttributeName': 'Nombre',
                'KeyType': 'HASH'  # Partition key
            },
            {
                'AttributeName': 'Timestamp',
                'KeyType': 'RANGE'  # Sort key
            }
        ],
        AttributeDefinitions=[
            {
                'AttributeName': 'Nombre',
                'AttributeType': 'S'
            },
            {
                'AttributeName': 'Timestamp',
                'AttributeType': 'S'
            }
        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': 30,
            'WriteCapacityUnits': 30
        }
    )
    return render_template('index.html')
