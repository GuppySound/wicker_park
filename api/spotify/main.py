from flask import Blueprint,request
import config
import requests
import json

spotify_routes = Blueprint('spotify_routes', __name__)

def parseUserTokens(request):
    user_id = request.args.get('id')
    access_token = request.args.get('access_token')
    refresh_token = request.args.get('refresh_token')
    assert user_id or (access_token and refresh_token), "Request must include either User ID or access and refresh tokens"
    if not access_token or not refresh_token:
        userRes = requests.get(f'{config.URL}{config.API_PREFIX}/users/getUser', params={'id': userId})
        user = userRes.json()
        access_token = user['spotify_access_token']
        refresh_token = user['spotify_refresh_token']
    return user_id, access_token, refresh_token

@spotify_routes.route('/me', methods=['GET'])
def getMe():
    try:
        user_id, access_token, refresh_token = parseUserTokens(request)

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
        user_id, access_token, refresh_token = parseUserTokens(request)

        headers = {'Authorization': f'Bearer {access_token}'}
        currently_playing = requests.get('https://api.spotify.com/v1/me/player/currently-playing', headers=headers)
        if currently_playing.status_code == 401:
            access_token = refreshToken(refresh_token, user_id)
            headers = {'Authorization': f'Bearer {access_token}'}
            currently_playing = requests.get(f'https://api.spotify.com/v1/me/player/currently-playing', headers=headers)

        if currently_playing.status_code == 204:
            params = {'limit': 5}
            recently_played = requests.get(f'https://api.spotify.com/v1/me/player/recently-played', headers=headers, params=params)
        else:
            recently_played = None

        updatePayload = {
            'spotify_currently_playing': dict(currently_playing.json()) if currently_playing.status_code == 200 else None,
            'spotify_recently_played': dict(recently_played.json()['items'][0]) if recently_played else None
        }
        updateArgs = {'id': user_id}

        # updates user state in Firebase
        requests.post(f'{config.URL}{config.API_PREFIX}/users/updateUser', params=updateArgs, json=updatePayload)
        return json.dumps(updatePayload)
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
