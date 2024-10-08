import sqlite3
import streamlit as st
import os
import io
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError
from google.oauth2.service_account import Credentials

SCOPES = ['https://www.googleapis.com/auth/drive.file']


# Authenticate using the service account
def authenticate_gdrive():
    # Load the service account credentials
    creds = service_account.Credentials.from_service_account_file(
        'credentials.json',
        scopes=['https://www.googleapis.com/auth/drive']
    )
    return creds


# Download SQLite database from Google Drive
def download_db_from_drive(service, file_id, file_name=None):
    request = service.files().get_media(fileId=file_id)
    fh = io.FileIO(file_name, 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()


def upload_db_to_drive(service, db_name, file_id):
    """Uploads or updates the SQLite database file to Google Drive.

    Args:
        service: Authenticated Google Drive service instance.
        db_name: Name of the database file to upload.
        file_id: Optional; ID of the file to update. If None, a new file will be created.

    Returns:
        The ID of the uploaded or updated file.
    """
    try:
        # Define the metadata for the file (with correct MIME type for SQLite)
        file_metadata = {
            'name': db_name,
            'mimeType': 'application/x-sqlite3'  # SQLite file MIME type
        }

        # Create media file upload
        media = MediaFileUpload(db_name, mimetype='application/x-sqlite3')

        if file_id:  # If updating an existing file
            try:
                # Attempt to retrieve the file to ensure it exists
                service.files().get(fileId=file_id).execute()

                # Proceed to update the file
                file = service.files().update(
                    fileId=file_id,
                    body=file_metadata,
                    media_body=media
                ).execute()

                st.success(f"Database updated successfully! File ID: {file.get('id')}")

                # Log the update success for debugging
                st.write(f"File metadata after update: {file}")

            except HttpError as e:
                if e.resp.status == 404:
                    st.error("File not found. Please check the file ID.")
                    return None  # Return None to indicate failure
                else:
                    st.error(f"An error occurred: {e}")
                    return None  # Return None to indicate failure
        else:  # If creating a new file
            # Create the file on Google Drive
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            st.success(f"Database uploaded successfully! File ID: {file.get('id')}")

            # Log the create success for debugging
            st.write(f"File metadata after creation: {file}")

        return file.get('id')  # Return the file ID

    except HttpError as error:
        st.error(f"An error occurred: {error}")
        return None  # Return None to indicate failure


# Connect to SQLite database
def connect_db(db_name):
    return sqlite3.connect(db_name)


def list_files(service):
    """Lists the files in Google Drive to help verify file IDs."""
    results = service.files().list(pageSize=10, fields="nextPageToken, files(id, name)").execute()
    items = results.get('files', [])
    if not items:
        st.write("No files found.")
    else:
        st.write("Files:")
        for item in items:
            st.write(f"{item['name']} ({item['id']})")


def main():
    st.title("SQLite Database with Google Drive Storage")

    # Build the Drive service
    creds = authenticate_gdrive()
    service = build('drive', 'v3', credentials=creds)

    # File ID of the SQLite database in Google Drive
    file_id = '12M9HJqSSmS-Dc4jO9ejvKSOf3Ir91X5-'
    db_name = 'tracking_expenses_app.db'

    # Download the SQLite file from Google Drive
    if not os.path.exists(db_name):
        download_db_from_drive(service, file_id, db_name)

    # Connect to the SQLite database
    conn = connect_db(db_name)
    c = conn.cursor()

    # Create table if it doesn't exist
    c.execute('''
        CREATE TABLE IF NOT EXISTS purchases_x (
            purchase_id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            category TEXT NOT NULL,
            purchase_amount REAL NOT NULL
        )
    ''')

    # Streamlit UI for adding data
    item_name = st.text_input("Item Name")
    category = st.text_input("Category")
    purchase_amount = st.number_input("Purchase Amount", min_value=0.0, step=0.01)

    if st.button("List Files"):
        list_files(service)

    if st.button("Add Purchase"):
        c.execute('''
            INSERT INTO purchases_x (item_name, category, purchase_amount)
            VALUES (?, ?, ?)
        ''', (item_name, category, purchase_amount))
        conn.commit()
        st.success("Purchase added!")

    if st.button("View Purchases"):
        c.execute('SELECT * FROM purchases_x')
        data = c.fetchall()
        st.write(data)

    if st.button("Upload DB to Google Drive"):
        file_id = file_id  # Replace with the actual file ID
        db_name = db_name  # The name of your database file
        result_id = upload_db_to_drive(service, db_name, file_id)

        if result_id is None:
            st.error("Failed to upload or update the database.")

    # Close the connection
    conn.close()


if __name__ == "__main__":
    main()
