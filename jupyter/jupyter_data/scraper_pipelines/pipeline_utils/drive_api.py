import os
import io
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload, MediaIoBaseDownload


class DriveApi:
    """
    A production-ready Google Drive API wrapper using environment variables
    for authentication, supporting both local file and in-memory operations.
    """

    def __init__(self):
        # 1. Load secrets from environment variables
        client_id = os.environ.get("GOOGLE_CLIENT_ID")
        client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
        refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN")

        if not all([client_id, client_secret, refresh_token]):
            raise ValueError(
                "Missing Google API environment variables. Ensure GOOGLE_CLIENT_ID, "
                "GOOGLE_CLIENT_SECRET, and GOOGLE_REFRESH_TOKEN are set."
            )

        # 2. Reconstruct the credentials object in memory
        self.creds = Credentials(
            token=None,  # Set to None so the library knows to fetch a new access token
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=["https://www.googleapis.com/auth/drive.file"],
        )

        # 3. Force an immediate refresh to validate the refresh token and populate the access token
        self.creds.refresh(Request())

        # 4. Build the Drive service
        self.service = build("drive", "v3", credentials=self.creds)

    def create_folder(self, folder_name: str, parent_folder_id: str = None) -> str:
        """
        Creates a folder and returns its Drive ID.
        """
        folder_metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_folder_id:
            folder_metadata["parents"] = [parent_folder_id]

        folder = (
            self.service.files().create(body=folder_metadata, fields="id").execute()
        )

        return folder.get("id")

    def upload_file(
        self,
        file_input,
        folder_id: str = None,
        filename: str = None,
        mimetype: str = "application/octet-stream",
    ) -> str:
        """
        Uploads a file from either a local file path or in-memory bytes.

        :param file_input: A string (filepath) OR bytes OR io.BytesIO object.
        :param folder_id: The Google Drive folder ID.
        :param filename: Required if uploading from memory. Optional if uploading a filepath.
        :param mimetype: The MIME type of the file (e.g., 'image/jpeg', 'application/json').
        """
        # 1. Handle in-memory raw bytes
        if isinstance(file_input, bytes):
            if not filename:
                raise ValueError(
                    "A filename must be provided when uploading raw bytes."
                )
            file_metadata = {"name": filename}
            if folder_id:
                file_metadata["parents"] = [folder_id]

            media = MediaIoBaseUpload(
                io.BytesIO(file_input), mimetype=mimetype, resumable=True
            )

        # 2. Handle in-memory BytesIO streams
        elif isinstance(file_input, io.BytesIO):
            if not filename:
                raise ValueError(
                    "A filename must be provided when uploading a BytesIO stream."
                )
            file_metadata = {"name": filename}
            if folder_id:
                file_metadata["parents"] = [folder_id]

            media = MediaIoBaseUpload(file_input, mimetype=mimetype, resumable=True)

        # 3. Handle local file paths
        elif isinstance(file_input, str):
            final_filename = filename if filename else os.path.basename(file_input)
            file_metadata = {"name": final_filename}
            if folder_id:
                file_metadata["parents"] = [folder_id]

            media = MediaFileUpload(file_input, mimetype=mimetype, resumable=True)

        else:
            raise TypeError(
                "file_input must be a file path (str), bytes, or io.BytesIO"
            )

        # Execute the upload
        file = (
            self.service.files()
            .create(body=file_metadata, media_body=media, fields="id")
            .execute()
        )

        return file.get("id")

    def get_file_in_memory(self, file_id: str) -> bytes:
        """
        Downloads a file directly into RAM.
        Ideal for passing directly to an AI API without saving to disk.
        """
        request = self.service.files().get_media(fileId=file_id)
        file_stream = io.BytesIO()
        downloader = MediaIoBaseDownload(file_stream, request)

        done = False
        while not done:
            status, done = downloader.next_chunk()

        return file_stream.getvalue()

    def get_file_to_disk(self, file_id: str, destination_path: str):
        """
        Downloads a file and saves it to your server's local file system.
        """
        request = self.service.files().get_media(fileId=file_id)

        with open(destination_path, "wb") as file_stream:
            downloader = MediaIoBaseDownload(file_stream, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()

    def get_folder_by_name(self, name: str, parent_folder_id: str = None) -> str:
        """Searches for a folder by name and returns its ID if it exists."""
        # Drive API search queries require escaping apostrophes
        safe_name = name.replace("'", "\\'")
        query = f"mimeType='application/vnd.google-apps.folder' and name='{safe_name}' and trashed=false"

        # Restrict the search to the specified parent, or the root directory
        if parent_folder_id:
            query += f" and '{parent_folder_id}' in parents"
        else:
            query += " and 'root' in parents"

        results = self.service.files().list(q=query, fields="files(id)").execute()
        items = results.get("files", [])

        return items[0]["id"] if items else None

    def get_or_create_path(self, path: str, root_folder_id: str = None) -> str:
        """
        Traverses a path like 'Market_Data/Puebla_Listings/Sedans' and creates missing folders.
        Returns the ID of the final target folder.
        """
        current_parent_id = root_folder_id
        # Split the path and ignore empty strings from trailing slashes
        folders = [f for f in path.split("/") if f.strip()]

        for folder in folders:
            # Check if the folder already exists in the current parent
            folder_id = self.get_folder_by_name(folder, current_parent_id)

            # If not, create it
            if not folder_id:
                folder_id = self.create_folder(folder, current_parent_id)

            # Step down into the new (or existing) folder for the next iteration
            current_parent_id = folder_id

        return current_parent_id
