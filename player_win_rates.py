# data_wrangler/player_win_rates.py
import json
import psycopg2
from decimal import Decimal
import argparse

class PlayerWinRateCalculator:
    def __init__(self, db_connection_string: str):
        self.conn = psycopg2.connect(db_connection_string)
    
    # Helper function to convert Decimal to float for JSON serialization
    def _decimal_to_float(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    
    def calculate_win_rates(self):
        """Calculate win rates for all players and update the database"""
        # First, collect all player participation and winnings
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    player_id, 
                    COUNT(*) as total_hands,
                    SUM(CASE WHEN winner = player_id THEN bb_won ELSE -bb_involved END) as total_bb
                FROM (
                    -- Subquery to unnest the player_ids array and calculate how much each player is involved in the hand
                    SELECT 
                        hand_id, 
                        unnest(player_ids) as player_id,
                        winner,
                        bb_won,
                        big_blind as bb_involved
                    FROM hand_histories
                ) as player_hands
                GROUP BY player_id
            """)
            
            player_stats = cur.fetchall()
        
        # Calculate mbb/h (assuming average 30 hands per hour for 6-max tables)
        player_win_rates = {}
        for player_id, total_hands, total_bb in player_stats:
            if total_hands < 50:  # Skip players with too few hands
                continue
                
            # Convert Decimal to float if needed
            if isinstance(total_bb, Decimal):
                total_bb = float(total_bb)
            
            # Calculate mbb/h (milli-big blinds per hour)
            mbb_per_hand = (total_bb * 1000) / total_hands
            hands_per_hour = 30  # Assumption: average hands per hour
            mbb_per_hour = mbb_per_hand * hands_per_hour
            
            player_win_rates[player_id] = {
                'total_hands': int(total_hands),
                'total_bb': total_bb,
                'mbb_per_hand': mbb_per_hand,
                'mbb_per_hour': mbb_per_hour
            }
        
        # Update the database with win rates
        with self.conn.cursor() as cur:
            for player_id, stats in player_win_rates.items():
                cur.execute("""
                    UPDATE hand_histories
                    SET player_win_rates = player_win_rates || %s::jsonb
                    WHERE %s = ANY(player_ids)
                """, (
                    json.dumps({player_id: stats}, default=self._decimal_to_float),
                    player_id
                ))
        
        self.conn.commit()
        return player_win_rates

def main():
    parser = argparse.ArgumentParser(description='Calculate player win rates and update database')
    parser.add_argument('--db-connection', required=True, help='Database connection string')
    
    args = parser.parse_args()
    
    calculator = PlayerWinRateCalculator(args.db_connection)
    win_rates = calculator.calculate_win_rates()
    
    # Print summary statistics
    top_players = sorted(
        [(player, stats['mbb_per_hour']) for player, stats in win_rates.items()],
        key=lambda x: x[1],
        reverse=True
    )[:10]
    
    print("\nTop 10 Players by Win Rate:")
    print("---------------------------")
    for player, rate in top_players:
        print(f"{player}: {rate:.2f} mbb/h")
    
    print("\nUpdated win rates for all players in the database")

if __name__ == "__main__":
    main()