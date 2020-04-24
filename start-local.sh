conda env update -f environment.yml
source activate wicker_park

export GOOGLE_APPLICATION_CREDENTIALS=$PWD"/wicker-park-secrets-cred.json"

python app.py
