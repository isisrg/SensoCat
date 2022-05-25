#Creates the application object as an instance of class Flask imported from the flask package
from crypt import methods
from flask import Flask

# FLASK
from flask import render_template, redirect, request
#APP
from app import app
from app.forms import UploadForm, NewStationForm
#BOTO3
import boto3
from boto3.dynamodb.conditions import Key
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
    # print(items_data)

    #Header values
    header = items_data.columns.values
    header = header.tolist()
    name_index = header.index('Nombre')
    latitude_index = header.index('Latitud')
    longitude_index = header.index('Longitud')
    sensor_index = header.index('Sensores')
    # print('Name index: ', name_index, ' Latitude index: ', latitude_index, ' Longitude index: ', longitude_index, ' Sensor index: ', sensor_index)
    # print('HEADER: ', header)

    #Number of rows of the csv
    row_size = items_data.shape[0]
    #Number of columns of the csv
    col_size = items_data.shape[1]

    for count_row in range(0, row_size):
        station_name = items_data.iloc[count_row,:].values[name_index]
        initial_date = reports_table.query(
            Limit = 1,
            # TRUE -> el más grande FALSE -> el más pequeño
            ScanIndexForward = True,
            KeyConditionExpression=Key('Nombre').eq(station_name)
        )
        initial_date = initial_date['Items']

        final_date = reports_table.query(
            Limit = 1,
            # TRUE -> el más grande FALSE -> el más pequeño
            ScanIndexForward = False,
            KeyConditionExpression=Key('Nombre').eq(station_name)
        )
        final_date = final_date['Items']

        if initial_date and final_date:
            initial_date = initial_date[0]['Timestamp']
            final_date = final_date[0]['Timestamp']
            print('Station: ', station_name, ' Initial date: ', initial_date, ' Final date: ', final_date)

            # stations_table.update_item(
            #     Key={'Nombre': str(station_name)},
            #     AttributeUpdates={
            #         'Fecha inicio': str(initial_date),
            #         'Fecha fin': str(final_date)
            #     },
            # )
            # test = '{"Nombre": "' +str(station_name)+ '", "Fecha inicio": "' +str(initial_date)+ '", "Fecha fin": "' +str(final_date)+ '"}'
            # print(test)
            # converted_data = json.loads(test)
            # print(converted_data)
            # stations_table.put_item(Item=converted_data)

        print(station_name)
    items_data=items_data.values.tolist()
    return render_template('home.html', title='Inicio', items_data=json.dumps(items_data), name_index=name_index, latitude_index=latitude_index, longitude_index=longitude_index)

@app.route('/home/modal')
def modal():
    #Returns all of the table's data
    table_data = stations_table.scan()
    #Returns the items from the data collected and saves it into pandas
    items_data = pd.DataFrame(table_data['Items'])
    #print(items_data)
    items_data=items_data.values.tolist()
    return render_template('modal.html', title='Home', items_data=json.dumps(items_data))

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
            labels.append(report['Timestamp'])
            data.append(report[sensor])

        return render_template('chart_table.html', title='Información', station_name=station_name, sensor=sensor, initial_date = initial_date, final_date = final_date, labels = labels, data = data)
    if request.method == 'POST':
        return redirect('/home')
        
@app.route('/about')
def about():
    return render_template('about.html', title='Sobre nosotros')

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
            #df.insert(0, 'Id', np.arange(start=1, stop=len(df)+1, step=1))
            table = 'Estaciones'
            mode = 0
            # initial_date = ''
            # final_date = ''

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

        for count_row in range(0, row_size):
            print(count_row)
            station_name = df.iloc[count_row,:].values[name_index]
            # with table.batch_writer() as batch:
            for count_col in range(0, col_size):
                row_values = df.iloc[count_row,:].values
                    
                if str(header[count_col]) == 'date':
                    header[count_col] = 'Timestamp'
                
                # if str(header[count_col]) == 'Sensores' and mode == 0:
                #     row_values[count_col] = str(row_values[count_col])
                #     row_values[count_col] = row_values[count_col].split(",")

                # if str(header[count_col]) == 'Timestamp' and mode == 1 or mode == 2:
                #     old_date = str(row_values[count_col])
                #     date = datetime.strptime(f'{old_date}', '%Y-%m-%dT%H:%M:%S')
                #     new_date = date.strftime('%d/%m/%Y %H:%M')
                #     row_values[count_col] = str(new_date)

                # if mode == 0:
                #     if str(header[count_col]) == 'Fecha-inicio':
                #         reports = reports_table.query(
                #             Limit = 1,
                #             # TRUE -> el más grande FALSE -> el más pequeño
                #             ScanIndexForward = True,
                #             KeyConditionExpression=Key('Nombre').eq(station_name)
                #         )
                #         reports = reports['Items']
                #         if reports:
                #             initial_date = reports_table.query(
                #                 Limit = 1,
                #                 # TRUE -> el más grande FALSE -> el más pequeño
                #                 ScanIndexForward = True,
                #                 KeyConditionExpression=Key('Nombre').eq(station_name)
                #             )
                #             initial_date = initial_date['Items'][0]['Timestamp']
                #             row_values[count_col] = str(initial_date)

                #     if str(header[count_col]) == 'Fecha-fin':
                #         reports = reports_table.query(
                #             Limit = 1,
                #             # TRUE -> el más grande FALSE -> el más pequeño
                #             ScanIndexForward = True,
                #             KeyConditionExpression=Key('Nombre').eq(station_name)
                #         )
                #         reports = reports['Items']
                #         if reports:
                #             final_date = reports_table.query(
                #                 Limit = 1,
                #                 # TRUE -> el más grande FALSE -> el más pequeño
                #                 ScanIndexForward = False,
                #                 KeyConditionExpression=Key('Nombre').eq(station_name)
                #             )
                #             final_date = final_date['Items'][0]['Timestamp']
                #             row_values[count_col] = str(final_date)

                #If the data is from a captor the date format is changed taking the seconds out
                if str(header[count_col]) == 'Timestamp' and mode == 1:
                    #If the data is from the captor20002, which has the date with a different format from all the other captors, is changed so it stays with the same format as all of the others
                    if(row_values[0] == 'captor20002'):
                        old_date = str(row_values[count_col])
                        date = datetime.strptime(f'{old_date}', '%Y-%m-%d %H:%M:%S')
                        # new_date = date.strftime('%d/%m/%Y %H:%M')
                        new_date = date.strftime('%Y-%m-%dT%H:%M')
                        row_values[count_col] = str(new_date)

                    #All the captors excluding the captor20002
                    else:
                        # old_date = str(row_values[count_col])
                        # date = datetime.strptime(f'{old_date}', '%d/%m/%Y %H:%M:%S')
                        # new_date = date.strftime('%d/%m/%Y %H:%M')
                        # row_values[count_col] = str(new_date)
                        old_date = str(row_values[count_col])
                        date = datetime.strptime(f'{old_date}', '%d/%m/%Y %H:%M:%S')
                        new_date = date.strftime('%Y-%m-%dT%H:%M')
                        row_values[count_col] = str(new_date)
                
                #If the data is from a reference station the date format is changed so it stays with the same format as the date in the captors
                if str(header[count_col]) == 'Timestamp' and mode == 2:
                    old_date = str(row_values[count_col])
                    date = datetime.strptime(f'{old_date}', '%Y-%m-%dT%H:%M')
                    # new_date = date.strftime('%d/%m/%Y %H:%M')
                    new_date = date.strftime('%Y-%m-%dT%H:%M')
                    row_values[count_col] = str(new_date)

                if count_col == 0: 
                    data_json = '{"' + str(header[count_col]) + '": "' + str(row_values[count_col]) + '"'     
                else:
                    data_json += ', "' + str(header[count_col]) + '": "' + str(row_values[count_col]) + '"'

                # if str(header[count_col]) == 'Timestamp' and mode == 1 or mode == 2:
                #     new_date = datetime.strptime(f'{new_date}', '%d/%m/%Y %H:%M')
                #     if count_row == 0 and mode == 1 or mode == 2:
                #         initial_date = new_date
                #         final_date = new_date
                #     if mode == 1 or mode == 1 or mode == 2:
                #         if new_date > final_date:
                #             final_date = new_date
                #         if new_date < initial_date:
                #             initial_date = new_date

                #     print('Initial date:' +initial_date.strftime('%d/%m/%Y %H:%M'))
                #     print('Final date: ' +final_date.strftime('%d/%m/%Y %H:%M'))
                
            data_json += '}'
            #Data converted to JSON format
            converted_data = json.loads(data_json)
            selected_table.put_item(Item=converted_data)

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
        #Number of rows of the csv
        row_size = items_data.shape[0]
        #Number of columns of the csv
        col_size = items_data.shape[1]

        #Primero equals 0 if its the first iteration on the Contaminantes column (also indicates wether the Contaminantes column exists or not)
        primero = 0

        data_json = '{"'

        for count_col in range(0, col_size):  
            if header[count_col] == 'Nombre': data = form_new_station.name.data
            if header[count_col] == 'Latitud': data = form_new_station.latitude.data
            if header[count_col] == 'Longitud': data = form_new_station.longitude.data
            if header[count_col] == 'Sensores': data = form_new_station.sensors.entries

            if header[count_col] == 'Sensores':
                # # data_json += ', "' + str(header[count_col]) + '": ['
                # data_json += ', "' + str(header[count_col]) + '": "'
                # for nested in form_new_station.sensors.entries:
                #     if primero == 0:
                # #         data_json += '"' + str(nested.data) + '"'
                #         data_json += str(nested.data)
                #         primero = 1
                #     else:
                # #         data_json += ', "' + str(nested.data) + '"'
                #         data_json += ',' + str(nested.data)
                # # data_json += ']'
                # data_json += '"'
                if count_col == 0:
                    data_json += str(header[count_col]) + '": "'
                else:
                    data_json += ', "' + str(header[count_col]) + '": "'
                sensors = ''
                for nested in data:
                    if primero == 0:
                        sensors += str(nested.data)
                        primero = 1
                    else:
                        sensors += ','+str(nested.data) 
                print(sensors)
                data_json += sensors+ '"'
            else:
                if str(header[count_col]) == 'Nombre' or str(header[count_col]) == 'Latitud' or str(header[count_col]) == 'Longitud':
                    data_json += ', "' + str(header[count_col]) + '": "' + str(data) + '"'

        #If Contaminantes column does not exists then creates one with the data specified by the user in the form
        # if primero == 0:
        #     data_json += ', "Contaminantes": ['
        #     for nested in form_new_station.sensors.entries:
        #         if primero == 0:
        #             data_json += '"' + str(nested.data) + '"'
        #             primero = 1
        #         else:
        #             data_json += ', "' + str(nested.data) + '"'
        #     data_json += ']'

        data_json += '}'
        print(data_json)
        #Data converted to JSON format
        converted_data = json.loads(data_json)
        dynamodb = boto3.resource('dynamodb')
        #Indicates which table is going to be used
        selected_table = dynamodb.Table('Estaciones')
        selected_table.put_item(Item=converted_data)
        return render_template('submit_station.html', title='Estación', form_new_station=form_new_station)


@app.route('/index')
def index():
    return render_template('index.html')
