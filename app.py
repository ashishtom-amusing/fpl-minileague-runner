import json
import requests
from flask import Flask, render_template, request, jsonify
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

app = Flask(__name__)

BASE_URL = "https://fantasy.premierleague.com/api/"
MAX_WORKERS = 10  # Concurrent API requests


def fetch_data(url, timeout=10):
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code != 200:
            return None
        return response.json()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


def fetch_league_data(league_id):
    """Fetch all teams from the league by handling pagination"""
    all_results = []
    page = 1

    while True:
        url = BASE_URL + f"leagues-classic/{league_id}/standings/?page_standings={page}"
        data = fetch_data(url)

        if not data or 'standings' not in data:
            break

        results = data['standings']['results']
        if not results:
            break

        all_results.extend(results)

        if not data['standings'].get('has_next', False):
            break

        page += 1

    if all_results:
        data['standings']['results'] = all_results

    return data


def fetch_manager_history(team_id):
    url = BASE_URL + f"entry/{team_id}/history/"
    return fetch_data(url)


def get_gw_leaderboard(league_id, gameweek):
    """Fetch league data and create leaderboard with parallel processing"""
    league_data = fetch_league_data(league_id)
    
    if not league_data:
        return None, "Failed to fetch league data"
    
    managers = league_data['standings']['results']
    leaderboard = []
    
    # Fetch history for all managers in parallel
    def fetch_manager_gw_data(manager):
        team_id = manager['entry']
        history = fetch_manager_history(team_id)
        
        if history and len(history['current']) >= gameweek:
            gw_points = history['current'][gameweek - 1]['points']
            transfer_cost = history['current'][gameweek - 1]['event_transfers_cost']
            net_points = gw_points - transfer_cost
            
            return {
                'manager_name': manager['entry_name'],
                'player_name': manager['player_name'],
                'team_id': manager['entry'],
                'gw_points': gw_points,
                'transfer_cost': transfer_cost,
                'net_points': net_points,
                'total_points': manager['total'],
                'overall_rank': manager['rank']
            }
        return None
    
    # Use ThreadPoolExecutor for parallel requests
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(fetch_manager_gw_data, mgr) for mgr in managers]
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                leaderboard.append(result)
    
    leaderboard.sort(key=lambda x: x['gw_points'], reverse=True)
    
    return leaderboard, None


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/leaderboard', methods=['POST'])
def leaderboard():
    try:
        gameweek = int(request.form.get('gameweek'))
        league_id = int(request.form.get('league_id'))
        
        leaderboard_data, error = get_gw_leaderboard(league_id, gameweek)
        
        if error:
            return jsonify({'error': error}), 400
        
        return jsonify({
            'gameweek': gameweek,
            'league_id': league_id,
            'leaderboard': leaderboard_data,
            'total_managers': len(leaderboard_data)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
