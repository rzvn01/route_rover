import sqlite3


class TripInfoDatabase:
    def __init__(self, database_path='trip_info.db'):
        self.connection = sqlite3.connect(database_path)
        self.cursor = self.connection.cursor()

    def create_table(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS trip_info (
                id INTEGER PRIMARY KEY,
                start_address TEXT,
                end_address TEXT,
                total_time REAL,
                total_distance REAL,
                route_description TEXT
            )
        ''')
        self.connection.commit()

    def insert_trip_info(self, start_address, end_address, total_time, total_distance, route_description):
        self.cursor.execute('''
            INSERT INTO trip_info (start_address, end_address, total_time, total_distance, route_description)
            VALUES (?, ?, ?, ?, ?)
        ''', (start_address, end_address, total_time, total_distance, route_description))
        self.connection.commit()

    def retrieve_trip_info(self):
        self.cursor.execute("SELECT * FROM trip_info")
        return self.cursor.fetchall()

    def delete_trip_info(self, id):
        """
        Delete trip information based on the start address.

        Parameters:
        - start_address (str): The start address of the trip to be deleted.
        """
        self.cursor.execute('''
               DELETE FROM trip_info
               WHERE id = ?
           ''', (id,))

        self.connection.commit()

    def close_connection(self):
        self.connection.close()

