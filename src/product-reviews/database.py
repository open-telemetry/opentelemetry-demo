#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# Python
import os
import simplejson as json

# MySQL
import mysql.connector
from mysql.connector import Error

def must_map_env(key: str):
    value = os.environ.get(key)
    if value is None:
        raise Exception(f'{key} environment variable must be set')
    return value

# Retrieve MySQL environment variables
db_host = must_map_env('MYSQL_HOST')
db_port = must_map_env('MYSQL_PORT')
db_user = must_map_env('MYSQL_USER')
db_password = must_map_env('MYSQL_PASSWORD')
db_name = must_map_env('MYSQL_DATABASE')

def fetch_product_reviews(product_id):
    try:
        return json.dumps(fetch_product_reviews_from_db(product_id), use_decimal=True)
    except Exception as e:
        return json.dumps({"error": str(e)})

def fetch_product_reviews_from_db(request_product_id):

    connection = None

    try:
        with mysql.connector.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            database=db_name
        ) as connection:

            with connection.cursor() as cursor:
                # Define the SQL query
                query = "SELECT username, description, score FROM productreviews WHERE product_id= %s"

                # Execute the query
                cursor.execute(query, (request_product_id, ))

                # Fetch all the rows from the query result
                records = cursor.fetchall()
                return records

    except Error as e:
        raise e
    finally:
        if connection is not None:
            try:
                connection.close()
            except Error as e:
                pass