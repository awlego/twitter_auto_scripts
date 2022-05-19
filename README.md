# twitter_auto_scripts
Scripts I automatically run to keep various twitter stuff up to date.

Right now this just keeps an auto-updated list of all my follows, so that I can use the list mode instead of the main timeline to help make sure I see all the tweets of the people I care about.

## Usage

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
For now, edit feed_update.py. Ideally this would be setup as imported environment variables, but I haven't gotten around to adding that yet. The important variables to change are
```
screen_name
list_name
list_id
```

Run the application
```
python feed_update.py /path/to/your/twitter_keys.json
```

This program can take a while to run because Twitter's API limits you pretty strictly with how often you can access it. The twitter API library I use automatically handles retries, so it will almost always complete, it just takes a while. With 271 following, mine takes 6 min 9 sec.

When the program runs, it will generate a log file that will look something like this:

`feed_update.log`
```
2021-08-10 06:38:11 INFO     Starting update
2021-08-10 06:44:20 INFO     current_list_ids: [1384258551795748866, ...]
2021-08-10 06:44:20 INFO     New followers found, to add: []
2021-08-10 06:44:20 INFO     Old followers found, to remove: []
2021-08-10 06:44:20 INFO     Finished update
```