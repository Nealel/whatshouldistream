# what should I stream?

This is a command line to identify good games in your steam library for streaming on twitch.


## how does it work?
It:
1. lists all your steam games using the steam API
2. finds how many people are currently streaming each game on twitch using the twitch API
3. finds game popularity data using steamspy API
4. applies your desired filters and sorts the remaining games by popularity

## Getting restarted
This app requires python and pip to be installed, as well as a steam API key and a twitch API key.
1. Install requirements.txt: `pip install -r requirements.txt` (you may need to use `pip3` instead of `pip``)
2. Create a .env file in the root directory with the following contents:
```
STEAM_API_KEY= your steam api key (need to sign up for it, be found at https://steamcommunity.com/dev/apikey)
STEAM_ID= your personal users steam id (can be found in your steam profile url)
TWITCH_CLIENT_ID= your twitch client id (need to sign up for it, can be found at https://dev.twitch.tv/console/apps)
TWITCH_CLIENT_SECRET= your twitch client secret
```
3. review and set configuration values at the top of `main.py`
4. run the app: `python main.py` (or `python3 main.py`)