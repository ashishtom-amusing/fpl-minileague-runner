import json
import requests
from flask import Flask, render_template, request, jsonify
from datetime import datetime

app = Flask(__name__)

BASE_URL = "https://fantasy.premierleague.com/api/"


def fetch_data(url):
    response = requests.get(url)
    if response.status_code != 200:
        return None
    return response.json()


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
    """Fetch league data and create leaderboard"""
    league_data = fetch_league_data(league_id)
    
    if not league_data:
        return None, "Failed to fetch league data"
    
    leaderboard = []
    
    for manager in league_data['standings']['results']:
        team_id = manager['entry']
        history = fetch_manager_history(team_id)
        
        if history and len(history['current']) >= gameweek:
            gw_points = history['current'][gameweek - 1]['points']
            transfer_cost = history['current'][gameweek - 1]['event_transfers_cost']
            net_points = gw_points - transfer_cost
            
            leaderboard.append({
                'manager_name': manager['entry_name'],
                'player_name': manager['player_name'],
                'team_id': manager['entry'],
                'gw_points': gw_points,
                'transfer_cost': transfer_cost,
                'net_points': net_points,
                'total_points': manager['total'],
                'overall_rank': manager['rank']
            })
    
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
