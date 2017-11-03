# -*- coding: utf-8 -*-

import os
import shutil
import sys
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
from urlparse import parse_qs
from os.path import basename
from zipfile import ZipFile

addon = xbmcaddon.Addon()
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

api_url = 'temp_url'

if xbmcvfs.exists(temp_dir):
    shutil.rmtree(temp_dir)
xbmcvfs.mkdirs(temp_dir)


def logger(message):
    xbmc.log(u"%{0} - %{1}".format(__name__, message).encode('utf-8'))


def show_notification(header, message):
    xbmc.executebuiltin('Notification({0}, {1})'.format(header, message))


def get_params(string=""):
    """
    {'action': 'manualsearch', 'languages': 'English', 'searchstring': 'test', 'preferredlanguage': 'English'}
    """

    param = []
    if string == "":
        paramstring = sys.argv[2]
    else:
        paramstring = string
    if len(paramstring) >= 2:
        params = paramstring
        cleanedparams = params.replace('?', '')
        if (params[len(params) - 1] == '/'):
            params = params[0:len(params) - 2]
        pairsofparams = cleanedparams.split('&')
        param = {}
        for i in range(len(pairsofparams)):
            splitparams = {}
            splitparams = pairsofparams[i].split('=')
            if (len(splitparams)) == 2:
                param[splitparams[0]] = splitparams[1]

    return param


def handle_search_action(params):
    try:
        current_video_name = player.getPlayingFile()
    except Exception as e:
        logger(e)
        show_notification(script_name, u'Video not playing!')
        return

    parsed_name = basename(current_video_name).rsplit('.', 1)
    if not parsed_name:
        show_notification(script_name, u'Invalid video name!')
        return

    parsed_name = parsed_name[0]

    request_params = dict(search_string=parsed_name, languages=params['languages'])
    # try:
    #     response = requests.get(api_url, request_params)
    # except Exception as e:
    #     logger(e)
    #     return


def handle_action(params):
    """
    :param params:
        {
            'action': string, one of: 'search', 'manualsearch', 'download',
            'languages': comma separated list of strings,
            'preferredlanguage': string,
            'searchstring': string, exists if 'action' param is 'manualsearch'
        }
    """
    logger(params)
    action = params['?action'][0]
    if action == 'search':
        logger('handling action: search')
        listitem = xbmcgui.ListItem(label='English',
                                    label2='test_subtitle.en.srt'
                                    )
        url = "plugin://%s/?action=download" % script_id

        xbmcplugin.addDirectoryItem(handle=plugin_handle, url=url, listitem=listitem, isFolder=False)

        # handle_search_action(params)

    elif action == 'manualsearch':
        handle_search_action(params)
    elif action == 'download':
        zip_file_location = '/home/tomislav/python_projects/kodi_titlovi_com/test_subtitle.zip'
        if not os.path.exists(zip_file_location) or not os.path.isfile(zip_file_location):
            show_notification(script_name, u'Subtitle file not found')
            return

        xbmc.sleep(500)
        xbmc.executebuiltin(('XBMC.Extract("%s","%s")' % (zip_file_location, temp_dir,)).encode('utf-8'), True)
        subtitle_file = xbmcvfs.listdir(zip_file_location)[1][0]
        subtitle_file = os.path.join(temp_dir, subtitle_file)
        if xbmcvfs.exists(subtitle_file):
            list_item = xbmcgui.ListItem(label=subtitle_file)
            xbmcplugin.addDirectoryItem(handle=plugin_handle, url=subtitle_file, listitem=list_item, isFolder=False)

        # handle_search_action(params)

    else:
        logger(u'Invalid action')
        show_notification(script_name, get_string(2103))

params_dict = parse_qs(sys.argv[2])

handle_action(params_dict)

xbmcplugin.endOfDirectory(plugin_handle)
