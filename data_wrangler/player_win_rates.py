# data_wrangler/player_win_rates.py
import json
import psycopg2
from decimal import Decimal
import argparse
from datetime import datetime
from collections import defaultdict

class PlayerWinRateCalculator:
    def __init__(self, db_connection_string: str):
        self.conn = psycopg2.connect(db_connection_string)
    
    # Helper function to convert Decimal to float for JSON serialization
    def _decimal_to_float(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    
    def identify_player_table_sessions(self, player_id):
        """
        Identify distinct table sessions for a player.
        A player might join and leave the same table multiple times, so we need to track
        continuous spans of time when they were at each table.
        """
        with self.conn.cursor() as cur:
            # First, get all tables where the player has played
            cur.execute("""
                SELECT DISTINCT table_name
                FROM hand_histories
                WHERE %(player_id)s = ANY(player_ids)
                  AND played_at IS NOT NULL
                  AND table_name IS NOT NULL
            """, {'player_id': player_id})
            
            tables = [row[0] for row in cur.fetchall()]
            
            # Track all table sessions
            all_table_sessions = []
            
            # For each table, get all hands and identify continuous sessions
            for table_name in tables:
                # Get all hands at this table, both with and without the player
                cur.execute("""
                    SELECT 
                        hand_id,
                        played_at,
                        %(player_id)s = ANY(player_ids) AS player_present,
                        CASE WHEN winner = %(player_id)s THEN bb_won
                             WHEN %(player_id)s = ANY(player_ids) THEN -big_blind 
                             ELSE 0 END AS bb_result
                    FROM hand_histories
                    WHERE table_name = %(table_name)s
                      AND played_at IS NOT NULL
                    ORDER BY played_at
                """, {'player_id': player_id, 'table_name': table_name})
                
                hands = cur.fetchall()
                
                # Identify continuous sessions where the player was present
                current_session = None
                
                for hand_id, played_at, player_present, bb_result in hands:
                    if player_present:
                        if current_session is None:
                            # Start a new session
                            current_session = {
                                'table_name': table_name,
                                'start_time': played_at,
                                'end_time': played_at,
                                'hands': [(hand_id, played_at, bb_result)],
                                'total_bb': bb_result if bb_result is not None else 0
                            }
                        else:
                            # Continue the current session
                            current_session['end_time'] = played_at
                            current_session['hands'].append((hand_id, played_at, bb_result))
                            current_session['total_bb'] += bb_result if bb_result is not None else 0
                    else:
                        # Player not present in this hand
                        if current_session is not None:
                            # Finalize current session and add to list
                            current_session['duration'] = (current_session['end_time'] - current_session['start_time']).total_seconds() / 3600  # hours
                            current_session['hand_count'] = len(current_session['hands'])
                            all_table_sessions.append(current_session)
                            current_session = None
                
                # Don't forget to add the last session for this table
                if current_session is not None:
                    current_session['duration'] = (current_session['end_time'] - current_session['start_time']).total_seconds() / 3600  # hours
                    current_session['hand_count'] = len(current_session['hands'])
                    all_table_sessions.append(current_session)
            
            return all_table_sessions
    
    def calculate_player_table_stats(self, player_id):
        """
        Calculate statistics for a player based on distinct table sessions.
        """
        # Get all table sessions for this player
        table_sessions = self.identify_player_table_sessions(player_id)
        
        if not table_sessions:
            return {
                'total_hands': 0,
                'total_bb': 0,
                'active_hours': 0,
                'hands_per_hour': 30,  # default
                'mbb_per_hand': 0,
                'mbb_per_hour': 0,
                'tables': 0,
                'table_sessions': 0,
                'table_data': []
            }
        
        # Calculate metrics for each table session
        table_data = []
        for session in table_sessions:
            # Calculate hands per hour for this session
            if session['duration'] < 0.25:  # Less than 15 minutes
                # Ensure minimum duration to avoid division by very small numbers
                hands_per_hour = session['hand_count'] / 0.25  
            else:
                hands_per_hour = session['hand_count'] / session['duration']
            
            # Calculate mbb metrics
            mbb_per_hand = (session['total_bb'] * 1000) / session['hand_count'] if session['hand_count'] > 0 else 0
            # Convert Decimal to float before multiplication
            mbb_per_hour = float(mbb_per_hand) * hands_per_hour
            
            table_data.append({
                'table': session['table_name'],
                'start': session['start_time'].isoformat(),
                'end': session['end_time'].isoformat(),
                'duration': session['duration'],
                'hands': session['hand_count'],
                'bb': float(session['total_bb']),
                'hands_per_hour': hands_per_hour,
                'mbb_per_hour': mbb_per_hour
            })
        
        # Calculate active time accounting for multi-tabling
        # First, create a timeline of when the player was active at any table
        timeline = []
        for session in table_sessions:
            timeline.append((session['start_time'], 1))  # 1 = start
            timeline.append((session['end_time'], -1))   # -1 = end
        
        # Sort the timeline by timestamp
        timeline.sort(key=lambda x: x[0])
        
        # Calculate total active time by tracking table count
        active_tables = 0
        last_time = None
        active_seconds = 0
        
        for time, change in timeline:
            # If player was active at at least one table, add to active time
            if active_tables > 0 and last_time is not None:
                active_seconds += (time - last_time).total_seconds()
            
            # Update table count
            active_tables += change
            last_time = time
        
        active_hours = active_seconds / 3600
        
        # Calculate overall metrics
        total_hands = sum(session['hand_count'] for session in table_sessions)
        total_bb = sum(session['total_bb'] for session in table_sessions)
        table_count = len(set(session['table_name'] for session in table_sessions))
        
        # Calculate weighted metrics based on active time
        if active_hours > 0:
            hands_per_hour = total_hands / active_hours
            mbb_per_hand = (total_bb * 1000) / total_hands if total_hands > 0 else 0
            # Convert Decimal to float before multiplication
            mbb_per_hour = float(mbb_per_hand) * hands_per_hour
        else:
            hands_per_hour = 30  # default
            mbb_per_hand = 0
            mbb_per_hour = 0
        
        return {
            'total_hands': total_hands,
            'total_bb': total_bb,
            'active_hours': active_hours,
            'hands_per_hour': hands_per_hour,
            'mbb_per_hand': mbb_per_hand,
            'mbb_per_hour': mbb_per_hour,
            'tables': table_count,
            'table_sessions': len(table_sessions),
            'table_data': table_data
        }
    
    def calculate_win_rates(self, min_hands=50):
        """Calculate win rates for all players using table-session-based analysis"""
        # First, ensure the players table exists with necessary columns
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    player_id TEXT PRIMARY KEY,
                    total_hands INTEGER,
                    total_bb NUMERIC,
                    mbb_per_hand NUMERIC,
                    mbb_per_hour NUMERIC,
                    hands_per_hour NUMERIC,
                    active_hours NUMERIC,
                    tables INTEGER,
                    table_sessions INTEGER,
                    table_data JSONB,
                    first_hand_at TIMESTAMP,
                    last_hand_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            self.conn.commit()
        
        # Get list of all players
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT unnest(player_ids) as player_id
                FROM hand_histories
                WHERE played_at IS NOT NULL
            """)
            
            player_ids = [row[0] for row in cur.fetchall()]
        
        # Calculate win rates for each player
        player_win_rates = {}
        print(f"Processing win rates for {len(player_ids)} players...")
        
        for i, player_id in enumerate(player_ids):
            if i % 50 == 0:
                print(f"Processed {i}/{len(player_ids)} players...")
            
            # Get the player's first and last hand timestamps
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        MIN(played_at) as first_hand,
                        MAX(played_at) as last_hand,
                        COUNT(*) as total_hands
                    FROM hand_histories
                    WHERE %s = ANY(player_ids)
                      AND played_at IS NOT NULL
                """, (player_id,))
                
                time_result = cur.fetchone()
                first_hand_at, last_hand_at, total_hands = time_result if time_result else (None, None, 0)
            
            if total_hands < min_hands:  # Skip players with too few hands
                continue
            
            # Calculate table-based win rates
            table_stats = self.calculate_player_table_stats(player_id)
            
            # Keep only important metrics for storage efficiency
            if table_stats['table_data']:
                # Sort sessions by end time, most recent first
                sorted_sessions = sorted(table_stats['table_data'], 
                                         key=lambda x: x['end'], 
                                         reverse=True)
                # Keep only the 20 most recent table sessions to avoid excessive storage
                table_data = sorted_sessions[:20]
            else:
                table_data = []
            
            # Update the players table
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO players (
                        player_id, 
                        total_hands, 
                        total_bb, 
                        mbb_per_hand, 
                        mbb_per_hour, 
                        hands_per_hour,
                        active_hours,
                        tables,
                        table_sessions,
                        table_data,
                        first_hand_at,
                        last_hand_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (player_id) DO UPDATE
                    SET total_hands = EXCLUDED.total_hands,
                        total_bb = EXCLUDED.total_bb,
                        mbb_per_hand = EXCLUDED.mbb_per_hand,
                        mbb_per_hour = EXCLUDED.mbb_per_hour,
                        hands_per_hour = EXCLUDED.hands_per_hour,
                        active_hours = EXCLUDED.active_hours,
                        tables = EXCLUDED.tables,
                        table_sessions = EXCLUDED.table_sessions,
                        table_data = EXCLUDED.table_data,
                        first_hand_at = EXCLUDED.first_hand_at,
                        last_hand_at = EXCLUDED.last_hand_at,
                        updated_at = NOW()
                """, (
                    player_id,
                    int(total_hands),
                    table_stats['total_bb'],
                    table_stats['mbb_per_hand'],
                    table_stats['mbb_per_hour'],
                    table_stats['hands_per_hour'],
                    table_stats['active_hours'],
                    table_stats['tables'],
                    table_stats['table_sessions'],
                    json.dumps(table_data),
                    first_hand_at,
                    last_hand_at
                ))
            
            player_win_rates[player_id] = {
                'total_hands': int(total_hands),
                'total_bb': table_stats['total_bb'],
                'mbb_per_hand': table_stats['mbb_per_hand'],
                'mbb_per_hour': table_stats['mbb_per_hour'],
                'hands_per_hour': table_stats['hands_per_hour'],
                'active_hours': table_stats['active_hours'],
                'tables': table_stats['tables'],
                'table_sessions': table_stats['table_sessions'],
                'first_hand_at': first_hand_at.isoformat() if first_hand_at else None,
                'last_hand_at': last_hand_at.isoformat() if last_hand_at else None
            }
        
        self.conn.commit()
        return player_win_rates

def main():
    parser = argparse.ArgumentParser(description='Calculate player win rates using table-based analysis')
    parser.add_argument('--db-connection', required=True, help='Database connection string')
    parser.add_argument('--min-hands', type=int, default=50, help='Minimum hands for player analysis')
    
    args = parser.parse_args()
    
    calculator = PlayerWinRateCalculator(args.db_connection)
    win_rates = calculator.calculate_win_rates(args.min_hands)
    
    # Print summary statistics
    top_players = sorted(
        [(player, stats['mbb_per_hour'], stats['hands_per_hour'], stats['active_hours'], stats['tables'], 
          stats['table_sessions'], stats['total_hands']) 
         for player, stats in win_rates.items()],
        key=lambda x: x[1],
        reverse=True
    )[:10]
    
    print("\nTop 10 Players by Win Rate:")
    print("---------------------------------------------------------------------------------------------")
    print("Player           Win Rate   Hands/Hr   Active Hrs   Tables   Sessions   Total Hands")
    print("---------------------------------------------------------------------------------------------")
    for player, rate, hands_hr, active_hrs, tables, sessions, total in top_players:
        print(f"{player[:15]:<15} {rate:8.2f}   {hands_hr:8.2f}   {active_hrs:10.2f}   {tables:6d}   {sessions:8d}   {total:11d}")
    
    print("\nUpdated win rates for all players in the database")

if __name__ == "__main__":
    main()