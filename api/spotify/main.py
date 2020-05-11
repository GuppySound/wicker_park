from flask import Blueprint,request,jsonify
import config
import requests
import json

spotify_routes = Blueprint('spotify_routes', __name__)

def parseUserTokens(data):
    user_id = data.get('id')
    access_token = data.get('access_token')
    refresh_token = data.get('refresh_token')
    assert user_id or (access_token and refresh_token), "Request must include either User ID or access and refresh tokens"
    if not access_token or not refresh_token:
        userRes = requests.get(f'{config.URL}{config.API_PREFIX}/users/getUser', params={'id': user_id})
        user = userRes.json()
        access_token = user['spotify_access_token']
        refresh_token = user['spotify_refresh_token']
    return user_id, access_token, refresh_token

def parseSpotifyPlayback(data):
    item = data.get('item', data.get('track'))
    return {
        'id': item.get('id'),
        'spotify_uri': item.get('uri'),
        'track_name': item.get('name'),
        'artist_name': ", ".join([i['name'] for i in item.get('artists')]) if
        'artists' in item else item.get('show', {}).get('publisher'),
        'is_playing': data.get('is_playing', False),
        'is_active': data.get('is_playing') is not None,
        'progress_ms': data.get('progress_ms'),
        'duration_ms': item.get('duration_ms'),
        'played_at': data.get('played_at')
    } if item else None

@spotify_routes.route('/me', methods=['GET'])
def getMe():
    try:
        user_id, access_token, refresh_token = parseUserTokens(request.args)
        headers = {'Authorization': f'Bearer {access_token}'}
        res = requests.get('https://api.spotify.com/v1/me', headers=headers)
        if res.status_code == 401:
            access_token = refreshToken(refresh_token, user_id)
            params = {'access_token': access_token}
            res = requests.get('https://api.spotify.com/v1/me', params=params)
        return res.json()
    except Exception as e:
        return f"An Error Occured: {e}"

# TODO: add functionality to automatically refresh if necessary (maybe put in model?)

# TODO: we should enable some batching on this endpoint - especially as it is used to get current status of following list
@spotify_routes.route('/me/playback', methods=['GET'])
def getPlayback():
    try:
        user_id, access_token, refresh_token = parseUserTokens(request.args)
        headers = {'Authorization': f'Bearer {access_token}'}
        params = {'additional_types': 'episode'}
        currently_playing = requests.get('https://api.spotify.com/v1/me/player/currently-playing', headers=headers, params=params)
        if currently_playing.status_code == 401:
            access_token = refreshToken(refresh_token, user_id)
            headers = {'Authorization': f'Bearer {access_token}'}
            currently_playing = requests.get(f'https://api.spotify.com/v1/me/player/currently-playing', headers=headers, params=params)

        if currently_playing.status_code == 204:
            params = {'limit': 1}
            recently_played = requests.get(f'https://api.spotify.com/v1/me/player/recently-played', headers=headers, params=params)
        else:
            recently_played = None

        updatePayload = {
            'spotify_playback': parseSpotifyPlayback(currently_playing.json() if currently_playing.status_code == 200 else
                                                     recently_played.json()['items'][0])
        }
        updateArgs = {'id': user_id}

        # updates user state in Firebase
        requests.post(f'{config.URL}{config.API_PREFIX}/users/updateUser', params=updateArgs, json=updatePayload)
        return json.dumps(updatePayload)
    except Exception as e:
        print(e)
        return f"An Error Occured: {e}"

@spotify_routes.route('/playback/update/<user_id>', methods=['POST'])
def updatePlayback(user_id):
    try:
        user_id, access_token, refresh_token = parseUserTokens({'id': user_id})
        headers = {'Authorization': f'Bearer {access_token}'}
        playback = request.get_json()['spotify_playback']
        print(playback)
        payload = {
          "uris": [playback['spotify_uri']],
          "position_ms": playback['progress_ms']-(min(playback['progress_ms'], 0))
        }
        play = requests.put(
            'https://api.spotify.com/v1/me/player/play',
            headers=headers,
            json=payload
        )
        if play.status_code == 401:
            access_token = refreshToken(refresh_token, user_id)
            headers = {'Authorization': f'Bearer {access_token}'}
            play = requests.put(
                'https://api.spotify.com/v1/me/player/play',
                headers=headers,
                json=payload
            )
        return jsonify(status_code=play.status_code)
    except Exception as e:
        print(e)
        return f"An Error Occured: {e}"

@spotify_routes.route('/playback/transfer/<from_user_id>/<to_user_id>', methods=['POST'])
def transferPlayback(from_user_id, to_user_id):
    try:
        payload = {'id': from_user_id}
        broadcaster_playback = requests.get(f'{config.URL}{config.API_PREFIX}/spotify/me/playback', params=payload)
        update = requests.post(f'{config.URL}{config.API_PREFIX}/spotify/playback/update/{to_user_id}', json=broadcaster_playback.json())
        return jsonify(update.json())
    except Exception as e:
        print(e)
        return f"An Error Occured: {e}"

def refreshToken(refreshToken, userId = None):
    try:
        tokensRes = requests.get(f'{config.URL}/auth/refreshToken', params={'refresh_token': refreshToken})
        tokens = tokensRes.json()
        if userId is not None:
            updateArgs = {'id': userId}
            updatePayload = { 'spotify_access_token': tokens.get('access_token') }
            if 'refresh_token' in tokens:
                updatePayload['refresh_token'] = tokens['refresh_token']
            requests.put(f'{config.URL}{config.API_PREFIX}/users/updateUser', params=updateArgs, data=updatePayload)
        return tokens.get('access_token')
    except Exception as e:
        print(e)
        return f"An Error Occured: {e}"
