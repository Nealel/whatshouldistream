from time import sleep

import requests
import json
import urllib.parse
import os
from dotenv import load_dotenv, dotenv_values
load_dotenv()

# User Configuration
max_streams = 0 # current streamers on twitch
game_tags = [] # steamspy genre tags ["Shooter"]
min_recent_playtime = 10 # average playtime over last 2 weeks
use_cache = True # faster but may give stale answers
min_release_date = None # todo make this work

game_ids_filename = "game_ids.txt"
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

        # Print the list of owned games
        # print(f"Total games owned: {len(games)}")
        # print("\nList of owned games:")
        # for game in games:
        #     name = game.get('name', 'Unknown Game')
        #     print(f" - {name}")

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
        else:
            # write new line to game_ids_filename
            with open(game_ids_filename, 'a') as file:
                file.write(f"{name},{game_ids[0]}\n")

        return game_ids[0]
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None


def read_game_ids_from_file():
    result = {}
    with open(game_ids_filename, 'r') as file:
        for line in file:
            # split on last , of the line
            key, value = line.strip().rsplit(',', 1)
            key = key.strip()
            value = value.strip()
            result[key] = value
    return result


def get_steamspy_data(game):
    #steamspy.com/api.php?request=appdetails&appid=730
    game_steam_id = game['steam_info']['appid']
    url = f"https://steamspy.com/api.php?request=appdetails&appid={game_steam_id}"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes
        data = response.json()
        print(data)
        return data
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None


print("getting steam games...")
games = get_owned_games(API_KEY, STEAM_ID)

print("authenticating with twitch...")
twitch_token = get_twitch_oauth_token(TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET)

game_data = {}

game_ids = read_game_ids_from_file()
print("resolving twitch data...")
for game in games:
    name = game['name']
    if name in game_ids:
        game_id = game_ids[name]
    # else:
        # game_id = get_game_id(name, twitch_token, TWITCH_CLIENT_ID)
    if game_id:
        game_data[name] = {
            'steam_info': game,
            'game_id': game_id,
        }


with open('game_data.json', 'r') as file:
    try:
        cached_game_data = json.load(file)
    except json.JSONDecodeError:
        print("failed to load cached game data")
        cached_game_data = {}

print("retrieving game data...")
for name in game_data:
    data = game_data[name]
    if use_cache and cached_game_data.get(name):
        game_data[name] = cached_game_data[name]
        continue
    else:
        game_data[name]['streams_count'] = get_streams_count(TWITCH_CLIENT_ID, twitch_token, data['game_id'])
        game_data[name]['steamspy_data'] = get_steamspy_data(data)
        sleep(1)


# write game data as json to file
with open('game_data.json', 'w') as file:
    json.dump(game_data, file)


print("filtering games...")
filtered_games = {}
for game, data in game_data.items():
    if data['streams_count'] > max_streams:
        continue

    if data['steamspy_data']['average_2weeks'] < min_recent_playtime:
        continue

    steamspy_tag_names = [key for key in data['steamspy_data']['tags']]
    tag_match = True
    for tag in game_tags:
        if tag not in steamspy_tag_names:
            tag_match = False
    if not tag_match:
        continue

    filtered_games[game] = data

print("sorting...")
sorted_games = sorted(filtered_games.items(), key=lambda x: x[1]['steamspy_data']['average_2weeks'], reverse=True)

# print all games
for game in sorted_games:
    print(f"{game[1]['steamspy_data']['average_2weeks']}\t {game[0]}")
    # print(f"{game[0]}: {game[1]['streams_count']} streams, current popularity: {game[1]['steamspy_data']['average_2weeks']}")
