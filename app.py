import json
import requests
from flask import Flask, render_template, request, jsonify
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

app = Flask(__name__)

BASE_URL = "https://fantasy.premierleague.com/api/"
MAX_WORKERS = 5  # Reduced for memory constraints on free tier

# Store progress data in memory (simple approach)
progress_data = {}


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


def get_gw_leaderboard(league_id, gameweek, request_id):
    """Fetch league data and create leaderboard with progress tracking"""
    league_data = fetch_league_data(league_id)
    
    if not league_data:
        return None, "Failed to fetch league data"
    
    managers = league_data['standings']['results']
    total_managers = len(managers)
    
    progress_data[request_id] = {
        'total': total_managers,
        'processed': 0,
        'status': 'processing'
    }
    
    leaderboard = []
    processed_count = 0
    
    # Fetch history for all managers in parallel
    def fetch_manager_gw_data(manager):
        nonlocal processed_count
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
        finally:
            processed_count += 1
            progress_data[request_id]['processed'] = processed_count
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
    
    leaderboard.sort(key=lambda x: x['gw_points'], reverse=True)
    progress_data[request_id]['status'] = 'completed'
    
    return leaderboard, None


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/leaderboard', methods=['POST'])
def leaderboard():
    try:
        import uuid
        import threading
        
        gameweek = int(request.form.get('gameweek'))
        league_id = int(request.form.get('league_id'))
        request_id = str(uuid.uuid4())
        
        # Start processing in background thread
        def process_data():
            leaderboard_data, error = get_gw_leaderboard(league_id, gameweek, request_id)
            if not error:
                progress_data[request_id]['data'] = leaderboard_data
        
        thread = threading.Thread(target=process_data)
        thread.start()
        
        # Return request ID for progress tracking
        return jsonify({'request_id': request_id})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/progress/<request_id>', methods=['GET'])
def get_progress(request_id):
    """Get progress of data fetching"""
    if request_id not in progress_data:
        return jsonify({'error': 'Invalid request ID'}), 404
    
    data = progress_data[request_id]
    
    if data['status'] == 'completed' and 'data' in data:
        # Return final data
        leaderboard_data = data['data']
        gameweek = request.args.get('gameweek', '')
        league_id = request.args.get('league_id', '')
        
        return jsonify({
            'status': 'completed',
            'gameweek': gameweek,
            'league_id': league_id,
            'leaderboard': leaderboard_data,
            'total_managers': len(leaderboard_data)
        })
    else:
        # Return progress
        return jsonify({
            'status': 'processing',
            'total': data['total'],
            'processed': data['processed'],
            'percentage': int((data['processed'] / data['total']) * 100) if data['total'] > 0 else 0
        })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
