import logging
import json
import os
import random
import string
import sys
import pprint
import threading
import tempfile

from urllib.parse import parse_qs
from typing import Dict, List
from http.server import HTTPServer, BaseHTTPRequestHandler
from enum import Enum

modules =  os.path.join(os.path.dirname(os.path.realpath(__file__)),'modules\\')
if modules not in sys.path:
    sys.path.insert(0, modules)

import modules.urllib3 as urllib3
import modules.requests as requests

class FFXIVAuthorizationResult(Enum):
    FAILED = 0
    FAILED_INVALID_CHARACTER_ID = 1
    FINISHED = 2

class FFXIVAuthorizationServer(BaseHTTPRequestHandler):
    backend = None

    def do_HEAD(self):
        return

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        try:       
            post_data = parse_qs(post_data)
        except:
            pass

        if self.path == '/login':
            self.do_POST_login(post_data)
        else:
            self.send_response(302)
            self.send_header('Location','/404')
            self.end_headers()

    def do_POST_login(self, data):

        data_valid = True

        if b'character_id' not in data:
            data_valid = False

        auth_result = False

        if data_valid:
            try:
                auth_result = self.backend.do_auth_character(data[b'character_id'][0].decode("utf-8"))
            except Exception:
                logging.exception("error on doing auth:")
 
        self.send_response(302)
        self.send_header('Content-type', "text/html")

        if auth_result == FFXIVAuthorizationResult.FINISHED:
            self.send_header('Location','/finished')
        else:
            self.send_header('Location','/login_failed')

        self.end_headers()


    def do_GET(self):
        status = 200
        content_type = "text/html"
        response_content = ""

        try:
            filepath = os.path.join(os.path.dirname(os.path.realpath(__file__)),'html\\%s.html' % self.path)

            if os.path.isfile(filepath):
                response_content = open(filepath).read()
            else:
                filepath = os.path.join(os.path.dirname(os.path.realpath(__file__)),'html\\404.html')

                if os.path.isfile(filepath):
                    response_content = open(filepath).read()
                else:
                    response_content = 'ERROR: FILE NOT FOUND'

            self.send_response(status)
            self.send_header('Content-type', content_type)
            self.end_headers()
            self.wfile.write(bytes(response_content, "UTF-8"))
        except Exception:
            logging.exception('FFXIVAuthorizationServer/do_GET: error on %s' % self.path)


class FFXIVAPI(object):
    API_DOMAIN = 'https://xivapi.com/'
    API_URL_CHARACTER = 'character/'
    LOCALSERVER_HOST = '127.0.0.1'
    LOCALSERVER_PORT = 13338
    INSTALL_URL = "https://gdl.square-enix.com/ffxiv/inst/ffxivsetup.exe"

    def __init__(self):
        self._server_thread = None
        self._server_object = None
        self._character_id = None
        self._account_info = None

    # 
    # Getters
    #

    def get_character_id(self) -> str:
        return self._character_id
        
    def get_character(self) -> List[str]:
        return self._account_info['Character']

    def get_character_name(self) -> str:
        return self._account_info['Character']['Name']

    def get_account_achievements(self) -> List[str]:
        return self._account_info['Achievements']['List']

    def get_account_friends(self) -> List[str]:
        return self._account_info['Friends']

    #
    # Authorization server
    #

    def auth_server_uri(self) -> str:
        return 'http://%s:%s/login' % (self.LOCALSERVER_HOST, self.LOCALSERVER_PORT)

    def auth_server_start(self) -> bool:

        if self._server_thread is not None:
            logging.warning('FFXIVAuthorization/auth_server_start: Auth server thread is already running')
            return False

        if self._server_object is not None:
            logging.warning('FFXIVAuthorization/auth_server_start: Auth server object is exists')
            return False

        FFXIVAuthorizationServer.backend = self
        self._server_object = HTTPServer((self.LOCALSERVER_HOST, self.LOCALSERVER_PORT), FFXIVAuthorizationServer)
        self._server_thread = threading.Thread(target = self._server_object.serve_forever)
        self._server_thread.daemon = True
        self._server_thread.start()

        return True

    def auth_server_stop(self) -> bool:
        if self._server_object is not None:
            self._server_object.shutdown()
            self._server_object = None
        else:
            logging.warning('FFXIVAuthorization/auth_server_stop: Auth server object is not exits')
            return False

        if self._server_thread is not None:
            self._server_thread.join()
            self._server_thread = None
        else:
            logging.warning('FFXIVAuthorization/auth_server_stop: Auth server thread is not running')
            return False

    def do_auth_character(self, character_id : str) -> FFXIVAuthorizationResult:
        (status_code, account_info) = self.__api_get_account_info(character_id)

        if account_info is None:
            return FFXIVAuthorizationResult.FAILED

        if status_code != 200:
            if 'Error' not in account_info:
                return FFXIVAuthorizationResult.FAILED

            if account_info['Ex'] == 'Lodestone\\Exceptions\\LodestoneNotFoundException':
                return FFXIVAuthorizationResult.FAILED_INVALID_CHARACTER_ID

            return FFXIVAuthorizationResult.FAILED

        self._character_id = character_id
        self._account_info = account_info

        return FFXIVAuthorizationResult.FINISHED

    def __api_get_account_info(self, character_id : str):
        resp = requests.get(self.API_DOMAIN + self.API_URL_CHARACTER + character_id, params={'data': 'AC,FR'})
        result = None

        try: 
            result = json.loads(resp.text)
        except Exception:
            logging.error('ffxivapi/__api_get_account_info: %s' % resp.text)

        return (resp.status_code, result)

    def get_installer(self):
        installer_path = os.path.join(tempfile.mkdtemp(), "ffxivsetup.exe")
        resp = requests.get(self.INSTALL_URL)

        if resp.status_code == 200:
            with open(installer_path, 'wb') as f:
                f.write(resp.content)

        return installer_path
