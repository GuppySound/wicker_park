conda env update -f environment.yml
source activate wicker_park

export GOOGLE_APPLICATION_CREDENTIALS=$PWD"/secrets_dev.json"

python app.py
