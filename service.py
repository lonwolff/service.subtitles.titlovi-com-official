# -*- coding: utf-8 -*-

import os
import shutil
import sys
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
import requests
import simplecache
from urlparse import parse_qs
from os.path import basename
from zipfile import ZipFile
from datetime import timedelta, datetime

addon = xbmcaddon.Addon()
video_info = xbmc.InfoTagVideo()

author = addon.getAddonInfo('author')
script_id = addon.getAddonInfo('id')
script_name = addon.getAddonInfo('name')
version = addon.getAddonInfo('version')
get_string = addon.getLocalizedString

script_dir = xbmc.translatePath(addon.getAddonInfo('path')).decode("utf-8")
profile = xbmc.translatePath(addon.getAddonInfo('profile')).decode("utf-8")
libs_dir = xbmc.translatePath(os.path.join(script_dir, 'resources', 'lib')).decode("utf-8")
temp_dir = xbmc.translatePath(os.path.join(profile, 'temp', '')).decode("utf-8")

player = xbmc.Player()

sys.path.append(libs_dir)

base_plugin_url = sys.argv[0]

plugin_handle = int(sys.argv[1])

api_url = 'https://kodi.titlovi.com/api/subtitles'

if not xbmcvfs.exists(temp_dir):
    xbmcvfs.mkdirs(temp_dir)

addon_cache = simplecache.SimpleCache()

def logger(message):
    xbmc.log(u"{0} - {1}".format(__name__, message).encode('utf-8'))


def show_notification(message):
    xbmc.executebuiltin('Notification({0}, {1})'.format(script_name, message))

class ActionHandler(object):
    def __init__(self, params):
        """
        :param params:
            {
                'action': string, one of: 'search', 'manualsearch', 'download',
                'languages': comma separated list of strings,
                'preferredlanguage': string,
                'searchstring': string, exists if 'action' param is 'manualsearch'
            }
        """

        self.params = params
        self.username = addon.getSetting("titlovi-username")
        self.password = addon.getSetting("titlovi-password")
        self.action = self.params['?action'][0]
        self.login_token = None

    def validate_params(self):
        """
        Method used for validating required parameters: 'username', 'password' and 'action'.
        """
        if not self.username or not self.password:
            show_notification(get_string(32005))
            return False
        if self.action not in ('search', 'manualsearch', 'download'):
            show_notification(get_string(2103))
            return False
        return True
    
    def get_prepared_language_param(self):
        language_mapping = {
            'English': 'English',
            'Croatian': 'Hrvatski',
            'Serbian': 'Srpski',
            'Slovenian': 'Slovenski',
            'Macedonian': 'Makedonski',
            'Bosnian': 'Bosanski'
        }
        subtitle_lang_string = self.params['languages']
        if not subtitle_lang_string:
            return None
        lang_list = 
        for key in language_mapping:
            if key in subtitle_lang_string:
                subtitle_lang_string.replace(key, language_mapping[key])
        
        if 'Serbo-Croatian' in 
        subtitle_lang_string.replace(',', '|')
        return subtitle_lang_string

        #TODO 'Serbo-Croatian'

    def handle_login(self):
        """
        Method used for sending user login request.
        
        OK return:
            {
                "ExpirationDate": datetime string (format: '%Y-%m-%dT%H:%M:%S.%f'),
                "Token": string,
                "UserId": integer,
                "UserName": string
            }

        Error return: None
        """
        logger('starting user login')
        login_params = dict(username=self.username, password=self.password, json=True)
        try:
            response = requests.post('{0}/gettoken'.format(api_url), params=login_params)
            logger('Response status: {0}'.format(response.status_code))  
            if response.status_code == requests.codes.ok:
                resp_json = response.json()
                logger('login response data: {0}'.format(resp_json))
                return resp_json
            elif resp_json.status_code == requests.codes.unauthorized:
                show_notification('Unauthorized, please check your login information!')
                return None
            else:
                return None
        except Exception as e:
            logger(e)
            return None

    def set_login_data(self, login_data):
        addon_cache.set('titlovi_com_login_data', login_data, expiration=timedelta(days=7))
        self.login_token = login_data.get('Token')
        self.user_id = login_data.get('UserId')

    def user_login(self):
        """
        Method used for logging in with titlovi.com username and password.
        After successful login data is stored in cache.
        """
        titlovi_com_login_data = addon_cache.get('titlovi_com_login_data')
        if not titlovi_com_login_data:
            logger('login data not found in cache')
            login_data = self.handle_login()
            if login_data is None:
                show_notification(u'Titlovi.com login error, try again')
                return False
            self.set_login_data(login_data)
            return True
        
        logger('user login data found in cache: {0}'.format(titlovi_com_login_data))
        expiration_date_string = titlovi_com_login_data.get('ExpirationDate')
        expiration_date = datetime.strptime(expiration_date_string, '%Y-%m-%dT%H:%M:%S.%f')
        date_delta = expiration_date - datetime.now()
        if date_delta.days <= 1:
            login_data = self.handle_login()
            if login_data is None:
                show_notification(u'Titlovi.com login error, try again')
                return False
            self.set_login_data(login_data)
            return True
        
        self.set_login_data(titlovi_com_login_data)
        return True
    
    def handle_action(self):
        """
        Method used for calling other action methods depending on 'action' parameter.
        """

        if self.action in ('search', 'manualsearch'):
            self.handle_search_action()
        elif self.action == 'download':
            self.handle_download_action()
        else:
            logger(u'Invalid action')
            show_notification(get_string(2103))

    def handle_search_action(self, search_string=None):
        """
        Method used for searching
        """
        logger('handling action: search')
    	
        search_string = self.params.get('searchstring')
        if not search_string:
            try:
                current_video_name = player.getPlayingFile()
            except Exception as e:
                logger(e)
                show_notification(u'Video not playing!')
                return

            parsed_name = basename(current_video_name).rsplit('.', 1)
            if not parsed_name:
                show_notification(u'Invalid video name!')
                return
            search_string = parsed_name[0]

        search_params = dict(token=self.login_token, userid=self.user_id, query=search_string)
        if self.params['languages']:
            search_params

        request_params = dict(search_string=search_string, languages=self.params['languages'])
        try:
            response = requests.get(api_url, request_params)
            response_data = response.json()
        except Exception as e:
            logger(e)
            return
        
        listitem = xbmcgui.ListItem(label='English',
                                    label2='test_subtitle.en.srt'
                                    )
        url = "plugin://%s/?action=download" % script_id

        xbmcplugin.addDirectoryItem(handle=plugin_handle, url=url, listitem=listitem, isFolder=False)

    def handle_download_action(self):
        zip_file_location = '/home/tomislav/python_projects/kodi_titlovi_com/test_subtitle.zip'
        if not os.path.exists(zip_file_location) or not os.path.isfile(zip_file_location):
            show_notification(u'Subtitle file not found')
            return

        xbmc.sleep(500)
        xbmc.executebuiltin(('XBMC.Extract("%s","%s")' % (zip_file_location, temp_dir,)).encode('utf-8'), True)
        subtitle_file = xbmcvfs.listdir(zip_file_location)[1][0]
        subtitle_file = os.path.join(temp_dir, subtitle_file)
        if xbmcvfs.exists(subtitle_file):
            list_item = xbmcgui.ListItem(label=subtitle_file)
            xbmcplugin.addDirectoryItem(handle=plugin_handle, url=subtitle_file, listitem=list_item, isFolder=False)

"""
params_dict:
{'action': 'manualsearch', 'languages': 'English', 'searchstring': 'test', 'preferredlanguage': 'English'}
"""
params_dict = parse_qs(sys.argv[2])
logger(params_dict)

action_handler = ActionHandler(params_dict)
if action_handler.validate_params():
    is_user_loggedin = action_handler.user_login()
    if is_user_loggedin:
        logger(u'user is logged in')
        # action_handler.handle_action()

xbmcplugin.endOfDirectory(plugin_handle)
