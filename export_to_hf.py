# data_wrangler/export_to_hf.py
from datasets import Dataset
import pandas as pd
import json
import psycopg2
import argparse

class HuggingFaceExporter:
    def __init__(self, db_connection_string: str):
        self.conn = psycopg2.connect(db_connection_string)
    
    def export_dataset(self, filter_query: str, dataset_name: str, push_to_hub: bool = False, hub_name: str = None):
        """Export a filtered dataset to HuggingFace format"""
        # Retrieve filtered data from the database
        with self.conn.cursor() as cur:
            cur.execute(f"""
                SELECT 
                    hand_id, 
                    pokergpt_format, 
                    winner, 
                    bb_won,
                    game_type,
                    big_blind
                FROM hand_histories
                WHERE {filter_query}
            """)
            
            rows = cur.fetchall()
            
        # Convert to pandas DataFrame
        df = pd.DataFrame(rows, columns=['hand_id', 'pokergpt_format', 'winner', 'bb_won', 'game_type', 'big_blind'])
        
        # Process the pokergpt_format column from JSON strings to dictionaries
        df['pokergpt_format'] = df['pokergpt_format'].apply(lambda x: json.loads(x) if isinstance(x, str) else x)
        
        # Create the dataset
        dataset = Dataset.from_pandas(df)
        
        # Push to HuggingFace Hub if requested
        if push_to_hub and hub_name:
            dataset.push_to_hub(hub_name)
            print(f"Dataset pushed to HuggingFace Hub: {hub_name}")
        
        # Save locally
        dataset.save_to_disk(dataset_name)
        print(f"Dataset saved locally to: {dataset_name}")
        
        return dataset
    
    def export_winning_player_dataset(self, min_win_rate: float = 500, min_hands: int = 100, dataset_name: str = "winning_players"):
        """Export a dataset filtered to only include hands from winning players"""
        filter_query = f"""
            EXISTS (
                SELECT 1 FROM jsonb_each(player_win_rates) AS p(player_id, stats)
                WHERE 
                    player_id = winner
                    AND (stats->>'mbb_per_hour')::float >= {min_win_rate}
                    AND (stats->>'total_hands')::int >= {min_hands}
            )
        """
        
        return self.export_dataset(filter_query, dataset_name)
    
    def export_preflop_dataset(self, min_win_rate: float = 500, dataset_name: str = "preflop_decisions"):
        """Export a dataset focused on preflop decisions by winning players"""
        filter_query = f"""
            has_preflop = TRUE
            AND EXISTS (
                SELECT 1 FROM jsonb_each(player_win_rates) AS p(player_id, stats)
                WHERE 
                    (stats->>'mbb_per_hour')::float >= {min_win_rate}
            )
        """
        
        return self.export_dataset(filter_query, dataset_name)

def main():
    parser = argparse.ArgumentParser(description='Export poker data to HuggingFace dataset')
    parser.add_argument('--db-connection', required=True, help='Database connection string')
    parser.add_argument('--min-win-rate', type=float, default=500, help='Minimum player win rate in mbb/h')
    parser.add_argument('--min-hands', type=int, default=100, help='Minimum hands played by a player')
    parser.add_argument('--dataset-name', default='winning_players', help='Local dataset name')
    parser.add_argument('--push-to-hub', action='store_true', help='Push to HuggingFace hub')
    parser.add_argument('--hub-name', help='HuggingFace hub dataset name (username/dataset)')
    
    args = parser.parse_args()
    
    exporter = HuggingFaceExporter(args.db_connection)
    dataset = exporter.export_winning_player_dataset(
        min_win_rate=args.min_win_rate,
        min_hands=args.min_hands,
        dataset_name=args.dataset_name
    )
    
    print(f"Exported {len(dataset)} hands to dataset")
    
    if args.push_to_hub and not args.hub_name:
        print("Warning: --push-to-hub requires --hub-name to be specified")

if __name__ == "__main__":
    main()