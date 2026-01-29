import mysql.connector

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="shachi",            
        password="shachi2410",
        database="grocery_db"
    )
conn = get_db_connection()
cursor = conn.cursor()
