# twitter_auto_scripts
Scripts I automatically run to keep various twitter stuff up to date.


Setup virtual env:
```
python3.8 -m venv env3.8
source /env3.8/bin/activate
```

Install requirements:
```
pip install --upgrade pip
pip install -r requirements.txt
```

Setup environment variables:
```
for now, edit feed_update.py. Ideally this would be setup as imported environment variables
```

Run the application
```
python feed_update.py
```