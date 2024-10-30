from time import sleep

import requests
import json
import urllib.parse
import os
from dotenv import load_dotenv, dotenv_values

load_dotenv()

# =========== User Configuration ============
# game filters
max_streams = 2 # current streamers on twitch
game_tags = [] # steamspy genre tags ["Shooter"]
popularity_metric = 'average_2weeks' # steamspy field name, other options: 'score_rank', 'average_forever', 'median_2weeks'
min_popularity = 1 # minimum value for the popularity metric above

# cache settings -- enabling cache is faster but data may be stale
use_steamspy_cache = True # used for popularity metrics
use_twitch_cache = True # used for current stream count

# ============ end user configuration ===========

game_data_filename = "game_data.json"

STEAM_ID = os.getenv("STEAM_ID")
API_KEY = os.getenv("API_KEY")
TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")


def get_owned_games(api_key, steam_id):
    # Steam API endpoint for getting owned games
    url = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"

    # Parameters for the API request
    params = {
        "key": api_key,
        "steamid": steam_id,
        "include_appinfo": "true",
        "format": "json"
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()  # Raise an exception for bad responses
        data = response.json()
        games = data['response'].get('games', [])

        if not games:
            print("No games found or the user's game list is private.")
            return

        return games

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
    except KeyError:
        print("Failed to parse the API response. The structure may have changed.")


def get_streams_count(client_id, oauth_token, game_id):
    url = f"https://api.twitch.tv/helix/streams?game_id={game_id}"
    headers = {
        'Client-ID': client_id,
        'Authorization': f'Bearer {oauth_token}'
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes
        data = response.json()

        # The 'data' key in the response contains the list of streams
        streams = data.get('data', [])
        return len(streams)

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None


def get_twitch_oauth_token(twitch_client_id, twitch_client_secret):
    twitch_auth_url = f"https://id.twitch.tv/oauth2/token?client_id={twitch_client_id}&client_secret={twitch_client_secret}&grant_type=client_credentials"
    try:
        response = requests.post(twitch_auth_url)
        response.raise_for_status()  # Raise an exception for bad status codes
        data = response.json()
        return data.get('access_token', None)
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None


def get_game_id(name, twitch_oauth_token, twitch_client_id):
    url_encoded_name = urllib.parse.quote(name)
    # todo handle punctuation
    url = f"https://api.twitch.tv/helix/games?name={url_encoded_name}"
    headers = {
        'Client-ID': twitch_client_id,
        'Authorization': f'Bearer {twitch_oauth_token}'
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes
        data = response.json()
        game_ids = [game['id'] for game in data.get('data', [])]
        if not game_ids:
            print(f"No game found with the name '{name}'")
            return None
        elif len(game_ids) > 1:
            print(f"Multiple games found with the name '{name}'. Using the first one.")

        return game_ids[0]
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None


def get_steamspy_data(game):
    #steamspy.com/api.php?request=appdetails&appid=730
    game_steam_id = game['steam_info']['appid']
    url = f"https://steamspy.com/api.php?request=appdetails&appid={game_steam_id}"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None


def enrich_and_filter_games(steam_games):
    with open('game_data.json', 'r') as file:
        try:
            cached_game_data = json.load(file)
        except json.JSONDecodeError:
            print("failed to load cached game data")
            cached_game_data = {}

    ignored_games = []
    with open('ignored_games.txt', 'r') as file:
        ignored_games = file.read().splitlines()

    game_data = {}
    all_game_data = {}
    print("retrieving game data...")
    for steam_game in steam_games:
        if steam_game['name'] in ignored_games:
            continue

        name = steam_game['name']
        data = {
            'steam_info': steam_game
        }

        cached_game = cached_game_data.get(name)

        if use_steamspy_cache and cached_game and cached_game.get('steamspy_data'):
            data['steamspy_data'] = cached_game_data[name]['steamspy_data']
        else:
            data['steamspy_data'] = get_steamspy_data(data)
            sleep(1) # respect rate limit

        # streamspy filters
        if data['steamspy_data'][popularity_metric] < min_popularity:
            all_game_data[name] = data
            continue

        steamspy_tag_names = [key for key in data['steamspy_data']['tags']]
        tag_match = True
        for tag in game_tags:
            if tag not in steamspy_tag_names:
                tag_match = False
        if not tag_match:
            all_game_data[name] = data
            continue

        if use_twitch_cache and cached_game and cached_game.get('streams_count'):
            data['streams_count'] = cached_game_data[name]['streams_count']
        else:
            if cached_game and cached_game.get('game_id'): # todo rename to twitch id
                data['game_id'] = cached_game_data[name]['game_id']
            else:
                data['game_id'] = get_game_id(name, twitch_token, TWITCH_CLIENT_ID)
            data['streams_count'] = get_streams_count(TWITCH_CLIENT_ID, twitch_token, data['game_id'])

        if data['streams_count'] > max_streams:
            all_game_data[name] = data
            continue

        all_game_data[name] = data
        game_data[name] = data

    # write cache
    with open('game_data.json', 'w') as file:
        json.dump(all_game_data, file)

    return game_data


print("getting steam games...")
games = get_owned_games(API_KEY, STEAM_ID)
print(f"found {len(games)} games")

print("authenticating with twitch...")
twitch_token = get_twitch_oauth_token(TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET)

print("resolving game data...")
filtered_games = enrich_and_filter_games(games)

print("sorting games...")
# sort games by popularity
sorted_games = sorted(filtered_games.items(), key=lambda x: x[1]['steamspy_data'][popularity_metric], reverse=True)

# print all games
for game in sorted_games:
    print(f"{game[1]['steamspy_data'][popularity_metric]}\t {game[0]}")
    # print(f"{game[0]}: {game[1]['streams_count']} streams, current popularity: {game[1]['steamspy_data']['average_2weeks']}")
