import json
import requests
from flask import Flask, render_template, request, jsonify, session
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

BASE_URL = "https://fantasy.premierleague.com/api/"
MAX_WORKERS = 5  # Reduced for memory constraints on free tier


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


def get_gw_leaderboard_with_progress(league_id, gameweek):
    """Fetch league data and create leaderboard - returns generator for progress"""
    league_data = fetch_league_data(league_id)
    
    if not league_data:
        yield {'error': 'Failed to fetch league data'}
        return
    
    managers = league_data['standings']['results']
    total_managers = len(managers)
    
    yield {
        'status': 'started',
        'total': total_managers,
        'processed': 0,
        'percentage': 0
    }
    
    leaderboard = []
    processed_count = 0
    
    # Fetch history for all managers in parallel
    def fetch_manager_gw_data(manager):
        try:
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
        except Exception as e:
            print(f"Error processing manager {manager.get('entry')}: {e}")
        return None
    
    # Process in smaller batches to reduce memory
    batch_size = 50
    for i in range(0, len(managers), batch_size):
        batch = managers[i:i + batch_size]
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(fetch_manager_gw_data, mgr) for mgr in batch]
            
            for future in as_completed(futures):
                result = future.result()
                if result:
                    leaderboard.append(result)
                processed_count += 1
                
                # Yield progress every 10 managers
                if processed_count % 10 == 0 or processed_count == total_managers:
                    yield {
                        'status': 'processing',
                        'total': total_managers,
                        'processed': processed_count,
                        'percentage': int((processed_count / total_managers) * 100)
                    }
    
    leaderboard.sort(key=lambda x: x['gw_points'], reverse=True)
    
    yield {
        'status': 'completed',
        'data': leaderboard
    }


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/leaderboard', methods=['GET'])
def leaderboard():
    try:
        gameweek = int(request.args.get('gameweek'))
        league_id = int(request.args.get('league_id'))
        
        def generate():
            for progress in get_gw_leaderboard_with_progress(league_id, gameweek):
                if 'error' in progress:
                    yield f"data: {json.dumps({'error': progress['error']})}\n\n"
                    return
                elif progress['status'] == 'completed':
                    yield f"data: {json.dumps({
                        'status': 'completed',
                        'gameweek': gameweek,
                        'league_id': league_id,
                        'leaderboard': progress['data'],
                        'total_managers': len(progress['data'])
                    })}\n\n"
                else:
                    yield f"data: {json.dumps(progress)}\n\n"
        
        return app.response_class(
            generate(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'
            }
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
