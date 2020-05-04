import config
import os
from flask import Blueprint,request,abort
from firebase_admin import credentials,initialize_app
import mock
from google.cloud import firestore
import google.auth.credentials
import json
import requests
import datetime
from flask_cors import CORS


if config.APP_ENV == 'Production':
    db = firestore.Client()
else:
    # TODO: differentiate test and integration environments (or just add flag to write to local mock database)
    # os.environ["FIRESTORE_DATASET"] = "test"
    # os.environ["FIRESTORE_EMULATOR_HOST"] = "localhost:8001"
    # os.environ["FIRESTORE_EMULATOR_HOST_PATH"] = "localhost:8001/firestore"
    # os.environ["FIRESTORE_HOST"] = "http://localhost:8001"
    # os.environ["FIRESTORE_PROJECT_ID"] = "test"
    #
    # credentials = mock.Mock(spec=google.auth.credentials.Credentials)
    # db = firestore.Client(project="test", credentials=credentials)
    print("initialize locally")
    cred = credentials.Certificate(f'secrets_dev.json')
    initialize_app(cred)
    db = firestore.Client(project='guppy-dev')

user_routes = Blueprint('user_routes', __name__)
CORS(user_routes)

usersRef = db.collection("users")

@user_routes.route('/getUser', methods=['GET'])
def getUser():
    userId = request.args.get('id')
    if userId:
        return json.dumps(usersRef.document(userId).get().to_dict())
    else:
        return "User not found.", 404

@user_routes.route('/createUser', methods=['POST', 'OPTIONS'])
def createUser():
    try:
        authCode = request.form.get('code', '')
        redirectUri = request.form.get('redirect_uri', '')
        payload = {'code': authCode, 'redirect_uri': redirectUri}
        tokensRes = requests.get(f'{config.URL}/auth/getTokens', params=payload)
        tokens = tokensRes.json()
        userRes = requests.get(f'{config.URL}{config.API_PREFIX}/spotify/me', params={'access_token': tokens.get('access_token'), 'refresh_token': tokens.get('refresh_token')})
        user = userRes.json()

        # only runs when user is found
        dbUser = usersRef.where(u'spotify_id', u'==', user['id']).stream()
        for u in dbUser:
            updateArgs = {'id': u.id}
            updatePayload = {
                'spotify_auth_code': authCode,
                'spotify_access_token': tokens['access_token'],
                'spotify_refresh_token': tokens['refresh_token']
            }
            requests.put(f'{config.URL}{config.API_PREFIX}/users/updateUser', params=updateArgs, data=updatePayload)
            return json.dumps({'id': u.id})

        # else create user
        userRef = usersRef.document()
        userRef.set({
            'is_live': False,
            'spotify_access_token': tokens['access_token'],
            'spotify_auth_code': authCode,
            'spotify_id': user['id'],
            'spotify_display_name': user['display_name'],
            'spotify_profile_picture': user['images'][0]['url'] if user['images'] else None,
            'spotify_refresh_token': tokens['refresh_token'],
            'created_at': datetime.datetime.now().strftime('%Y-%d-%mT%H:%M:%S')
        })
        return json.dumps({'id': userRef.id})
    except Exception as e:
        print(e)
        return f"An Error Occured: {e}"

@user_routes.route('/updateUser', methods=['PUT', 'POST'])
def updateUser():
    try:
        userId = request.args.get('id')
        usersRef.document(userId).update(request.get_json())
        return json.dumps({'success': True})
    except Exception as e:
        return f"An Error Occured: {e}"

@user_routes.route('/updateFollowing', methods=['POST', 'OPTIONS'])
def updatePlayback():
    try:
        userId = request.form.get('id')
        followingRef = usersRef.where("followers", "array_contains", userId)
        docs = followingRef.stream()
        for doc in docs:
            data = doc.to_dict()
            payload = {'id': doc.id, 'access_token': data['spotify_access_token'], 'refresh_token': data['spotify_refresh_token']}
            requests.get(f'{config.URL}{config.API_PREFIX}/spotify/me/playback', params=payload)
        return json.dumps({'success': True})

    except Exception as e:
        print(e)
        return f"An Error Occured: {e}"
