import configparser
import io
from apiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
from httplib2 import Http
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from googleapiclient.errors import HttpError


SCOPES = ['https://www.googleapis.com/auth/drive']


class Gdrive:
    def __init__(self):
        super().__init__()
        config = configparser.ConfigParser()
        config.read('config.ini')
        self.replayfolder = config['DRIVE']['replay']
        self.logfolder = config['DRIVE']['log']

    def download_replay(self):
        credentials = ServiceAccountCredentials.from_json_keyfile_name(
            'service_account.json', SCOPES)
        http_auth = credentials.authorize(Http())
        condition_list = [
            f"('{self.replayfolder}' in parents)",
            "(name contains '.rofl')"
        ]
        conditions = " and ".join(condition_list)
        drive_service = build('drive', 'v3', http=http_auth)
        results = drive_service.files().list(
            q=conditions,
            fields="nextPageToken, files(id, name)",
            pageSize=100,
        ).execute()
        files = results.get('files', [])
        filelist = []
        if files:
            for file in files:
                request = drive_service.files().get_media(fileId=file['id'])
                filename = file['name']
                filepath = f'data/replays/{filename}'
                fh = io.FileIO(filepath, mode='wb')
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
                filelist.append(filepath)
        return filelist

    def upload_log(self):
        credentials = ServiceAccountCredentials.from_json_keyfile_name(
            'service_account.json', SCOPES)
        http_auth = credentials.authorize(Http())
        try:
            # create drive api client
            service = build('drive', 'v3', http=http_auth)

            file_metadata = {
                'name': 'logdata',
                'mimeType': 'application/vnd.google-apps.spreadsheet',
                'parents': [self.logfolder]
            }
            media = MediaFileUpload('data/log/log.csv', mimetype='text/csv',
                                    resumable=True)
            file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()

        except HttpError:
            file = None

        return file
