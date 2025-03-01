import codecs
import re

import arrow

from slyguy import plugin, gui, settings, userdata, signals, inputstream
from slyguy.constants import PLAY_FROM_TYPES, PLAY_FROM_ASK, PLAY_FROM_LIVE, PLAY_FROM_START, MIDDLEWARE_PLUGIN

from .api import API
from .language import _
from .constants import *

api = API()

@signals.on(signals.BEFORE_DISPATCH)
def before_dispatch():
    api.new_session()
    plugin.logged_in = api.logged_in

@plugin.route('')
def home(**kwargs):
    folder = plugin.Folder(cacheToDisc=False)

    if not api.logged_in:
        folder.add_item(label=_(_.LOGIN, _bold=True), path=plugin.url_for(login), bookmark=False)
    else:
        folder.add_item(label=_(_.LIVE_TV, _bold=True), path=plugin.url_for(editorial, id=LINEAR_ID, title=_.LIVE_TV))
        _home(folder)

        if settings.getBool('bookmarks', True):
            folder.add_item(label=_(_.BOOKMARKS, _bold=True), path=plugin.url_for(plugin.ROUTE_BOOKMARKS), bookmark=False)

        folder.add_item(label=_.LOGOUT, path=plugin.url_for(logout), _kiosk=False, bookmark=False)

    folder.add_item(label=_.SETTINGS, path=plugin.url_for(plugin.ROUTE_SETTINGS), _kiosk=False, bookmark=False)

    return folder

def _home(folder):
    for row in api.navigation():
        if row['id'] == 'teams':
            continue

        if row['id'] == 'home':
            row['title'] = _.FEATURED

        folder.add_item(
            label = _(row['title'], _bold=True),
            path = plugin.url_for(page, id=row['path'], title=row['title']),
        )

@plugin.route()
def page(id, title, **kwargs):
    folder = plugin.Folder(title)

    for row in api.page(id):
        folder.add_item(
            label = row['title'],
            path = plugin.url_for(editorial, id=row['id'], title=row['title']),
        )

    return folder

@plugin.route()
def editorial(id, title, **kwargs):
    folder = plugin.Folder(title)
    now = arrow.utcnow()

    live_play_type = settings.getEnum('live_play_type', PLAY_FROM_TYPES, default=PLAY_FROM_ASK)

    for row in api.editorial(id):
        is_live = row.get('isLive', False)
        is_linear = row.get('type') == 'linear-channel'

        item = plugin.Item(
            label = row['title'],
            info  = {
                'plot': row.get('description'),
                'duration': row.get('duration', 0),
            },
            art   = {'thumb': row.get('imageUrl') or DEFAULT_IMG},
            path  = plugin.url_for(play, asset=row['id'], _is_live=is_live),
            playable = True,
            is_folder = False,
        )

        start_time = arrow.get(row['broadcastStartTime']) if 'broadcastStartTime' in row else None

        if start_time and start_time > now:
            item.label += start_time.to('local').format(_.DATE_FORMAT)

        elif is_linear:
            item.path = plugin.url_for(play, asset=row['id'], _is_live=is_live)

        elif is_live:
            item.label = _(_.LIVE, label=item.label)

            item.context.append((_.PLAY_FROM_LIVE, "PlayMedia({})".format(
                plugin.url_for(play, asset=row['id'], play_type=PLAY_FROM_LIVE, _is_live=is_live)
            )))

            item.context.append((_.PLAY_FROM_START, "PlayMedia({})".format(
            plugin.url_for(play, asset=row['id'], play_type=PLAY_FROM_START, _is_live=is_live)
            )))

            item.path = plugin.url_for(play, asset=row['id'], play_type=live_play_type, _is_live=is_live)

        folder.add_items(item)

    return folder

@plugin.route()
def login(**kwargs):
    username = gui.input(_.ASK_USERNAME, default=userdata.get('username', '')).strip()
    if not username:
        return

    userdata.set('username', username)

    password = gui.input(_.ASK_PASSWORD, hide_input=True).strip()
    if not password:
        return

    api.login(username=username, password=password)
    gui.refresh()

@plugin.route()
def logout(**kwargs):
    if not gui.yes_no(_.LOGOUT_YES_NO):
        return

    api.logout()
    gui.refresh()


@plugin.route()
@plugin.plugin_middleware()
def mpd_request(url, _data, _path, **kwargs):
    _data = _data.decode('utf8')

    ## OS1 HACK
    if '/OptusSport1/' in url:
        to_add = r'''\1\n
        <Representation id="1" width="1280" height="720" frameRate="50/1" bandwidth="5780830" codecs="avc1.640020"/>
        <Representation id="7" width="896" height="504" frameRate="50/1" bandwidth="3686399" codecs="avc1.640020"/>
        <Representation id="2" width="640" height="360" frameRate="50/1" bandwidth="2454399" codecs="avc1.640020"/>
        <Representation id="6" width="384" height="216" frameRate="50/1" bandwidth="1345630" codecs="avc1.640020"/>
        <Representation id="3" width="256" height="144" frameRate="50/1" bandwidth="852830" codecs="avc1.640020"/>
        '''
        if settings.getBool('h265', True):
            to_add += '<Representation id="8" width="1920" height="1080" frameRate="50/1" bandwidth="7135999" codecs="hvc1.1.6.H120.B0"/>\n<Representation id="5" width="1024" height="576" frameRate="50/1" bandwidth="3932799" codecs="hvc1.1.6.H120.B0"/>'
        _data = re.sub('(<Representation id="9" width="1280".*?>)', to_add, _data, 1)

    ## OS2 HACK
    elif '/OptusSport2/' in url:
        to_add = r'''\1\n
        <Representation id="7" width="1280" height="720" frameRate="50/1" bandwidth="5780830" codecs="avc1.640020"/>
        <Representation id="2" width="896" height="504" frameRate="50/1" bandwidth="3686399" codecs="avc1.640020"/>
        <Representation id="3" width="640" height="360" frameRate="50/1" bandwidth="2454399" codecs="avc1.640020"/>
        <Representation id="4" width="384" height="216" frameRate="50/1" bandwidth="1345630" codecs="avc1.640020"/>
        <Representation id="5" width="256" height="144" frameRate="50/1" bandwidth="852830" codecs="avc1.640020"/>
        '''
        if settings.getBool('h265', True):
            to_add += '<Representation id="8" width="1920" height="1080" frameRate="50/1" bandwidth="7135999" codecs="hvc1.1.6.H120.B0"/>\n<Representation id="1" width="1024" height="576" frameRate="50/1" bandwidth="3932799" codecs="hvc1.1.6.H120.B0"/>'
        _data = re.sub('(<Representation id="13" width="1280".*?>)', to_add, _data, 1)

    ## OS11/12 HACK
    elif '/OptusSport11/' in url or '/OptusSport12/' in url:
        to_add = r'''\1\n
        <Representation id="2" width="1280" height="720" frameRate="50/1" bandwidth="5780830" codecs="avc1.640020"/>
        <Representation id="4" width="896" height="504" frameRate="50/1" bandwidth="3686399" codecs="avc1.640020"/>
        <Representation id="5" width="640" height="360" frameRate="50/1" bandwidth="2454399" codecs="avc1.640020"/>
        <Representation id="6" width="384" height="216" frameRate="50/1" bandwidth="1345630" codecs="avc1.640020"/>
        <Representation id="7" width="256" height="144" frameRate="50/1" bandwidth="852830" codecs="avc1.640020"/>
        '''
        if settings.getBool('h265', True):
            to_add += '<Representation id="1" width="1920" height="1080" frameRate="50/1" bandwidth="7135999" codecs="hvc1.1.6.H120.B0"/>\n<Representation id="3" width="1024" height="576" frameRate="50/1" bandwidth="3932799" codecs="hvc1.1.6.H120.B0"/>'
        _data = re.sub('(<Representation id="9" width="1280".*?>)', to_add, _data, 1)

    with open(_path, 'wb') as f:
        f.write(_data.encode('utf8'))

@plugin.route()
@plugin.login_required()
def play(asset, play_type=PLAY_FROM_LIVE, **kwargs):
    play_type = int(play_type)

    from_start = False
    if play_type == PLAY_FROM_START or (play_type == PLAY_FROM_ASK and not gui.yes_no(_.PLAY_FROM, yeslabel=_.PLAY_FROM_LIVE, nolabel=_.PLAY_FROM_START)):
        from_start = True

    stream = api.play(asset, True, use_cmaf=inputstream.require_version('20.3.1'))

    item = plugin.Item(
        path = stream['url'],
        inputstream = inputstream.Widevine(
            license_key=stream['license']['@uri'],
        ),
        headers = HEADERS,
    )

    if stream['protocol'] == 'CMAF':
        item.inputstream.manifest_type = 'hls'
        item.inputstream.mimetype = 'application/vnd.apple.mpegurl'
    elif 'v6/OptusSport' in stream['url']:
        item.proxy_data['middleware'] = {stream['url']: {'type': MIDDLEWARE_PLUGIN, 'url': plugin.url_for(mpd_request, url=stream['url'])}}

    drm_data = stream['license'].get('drmData')
    if drm_data:
        item.headers['x-axdrm-message'] = drm_data

    if from_start:
        item.resume_from = 1

    return item

@plugin.route()
@plugin.merge()
def playlist(output, **kwargs):
    with codecs.open(output, 'w', encoding='utf8') as f:
        f.write(u'#EXTM3U x-tvg-url="{}"'.format(EPG_URL))

        for row in api.editorial(LINEAR_ID):
            if row.get('type') != 'linear-channel':
                continue

            f.write(u'\n#EXTINF:-1 tvg-id="{id}" tvg-logo="{logo}",{name}\n{url}'.format(
                id=row['channel']['id'], logo=row.get('imageUrl') or DEFAULT_IMG, name=row['title'], url=plugin.url_for(play, asset=row['id'], _is_live=True)))
