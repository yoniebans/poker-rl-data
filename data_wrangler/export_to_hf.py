# data_wrangler/export_to_hf.py
from datasets import Dataset
import pandas as pd
import json
import psycopg2
import argparse
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
import yaml
from dotenv import load_dotenv

# Import the PokerGPT formatter
from data_wrangler.pokergpt_formatter import PokerGPTFormatter

# Load environment variables from .env file
load_dotenv()

class HuggingFaceExporter:
    """
    Export poker hand history data to HuggingFace dataset format with PokerGPT prompt support.
    """
    
    def __init__(self, db_connection_string: str):
        """
        Initialize the exporter with database connection.
        
        Args:
            db_connection_string: PostgreSQL connection string
        """
        self.conn = psycopg2.connect(db_connection_string)
        self.formatter = PokerGPTFormatter()
    
    def _create_dataset_card(self, 
                           dataset_name: str, 
                           filter_description: str, 
                           sample_count: int, 
                           win_rate_threshold: Optional[float] = None,
                           min_hands: Optional[int] = None,
                           game_stage: Optional[str] = None,
                           pokergpt_format: bool = False) -> str:
        """
        Create a dataset card following HuggingFace guidelines.
        
        Args:
            dataset_name: Name of the dataset
            filter_description: Description of filtering criteria
            sample_count: Number of samples in the dataset
            win_rate_threshold: Minimum win rate for player inclusion
            min_hands: Minimum hands played for player inclusion
            game_stage: Game stage filter (e.g., 'preflop')
            pokergpt_format: Whether the dataset includes PokerGPT prompts
            
        Returns:
            Markdown formatted dataset card
        """
        # Get the current date in ISO format
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        # Create the dataset card in markdown format
        dataset_card = f"""---
annotations_creators:
  - machine-generated
language_creators:
  - found
languages:
  - en
licenses:
  - mit
source_datasets:
  - original
task_categories:
  - text-generation
  - reinforcement-learning
task_ids:
  - language-modeling
  - decision-making
pretty_name: {dataset_name}
size_categories:
  - 10K<n<100K
tags:
  - poker
  - decision-making
  - gaming
  - RL
---

# Dataset Card for {dataset_name}

## Dataset Description

### Dataset Summary

This dataset contains poker hand histories filtered for high-quality decision-making samples to train Poker-RL. It includes hands played by winning players with a minimum win rate of {win_rate_threshold} mbb/hour (milli-big blinds per hour) over at least {min_hands} hands.

{filter_description}

### Dataset Structure

The dataset contains {sample_count} hand histories structured in a format optimized for training poker AI models.

Each entry contains:
- `hand_id`: Unique identifier for the hand
- `pokergpt_format`: Structured JSON representation of the entire hand including player actions, bet sizes, and community cards
- `winner`: Player who won the hand
- `bb_won`: Amount won in big blinds
- `game_type`: Type of poker game (e.g., "Hold'em No Limit")
- `big_blind`: Size of the big blind
"""

        # Add PokerGPT-specific info if relevant
        if pokergpt_format:
            dataset_card += """
- `pokergpt_prompt`: Formatted prompt following the PokerGPT paper structure
- `action`: (Optional) The winning action for supervised training

The pokergpt_prompt field follows the exact format from the PokerGPT paper:
```
You are an experienced gambler. Now you need to assist me to make decisions in Texas Hold'em games. You have been provided with a series of observable information:

Player amount: [6], Currency: USD, Blind value: [0.02/0.05], Order: ['2', '3', '5', '6', '7', '9'], Seat 2 is small blind.
My cards: ['Th', 'Ah'], the characteristics of my cards: ["suit", "high", "close"], My seat: [Seat 2]
Stage: "PREFLOP", Public cards: ['**' '**' '**' '**' '**']
My rank: ["High"], Money: [3.92], Action: []
...
The pot value is [0.17]
The actions can be: ["fold", "raise", "call"]. What should I do? If I choose to "bet" or "raise", then how much?
```
"""

        dataset_card += f"""
### Data Collection and Processing

This dataset was created by:
1. Parsing PokerStars hand history files with robust error handling
2. Storing structured data in a PostgreSQL database
3. Calculating accurate player win rates using a table-based approach that:
   - Identifies distinct table sessions (when players join and leave tables)
   - Accounts for players leaving and rejoining the same table
   - Properly handles multi-tabling by tracking a timeline of active tables
   - Calculates precise active playing time for accurate hourly rates
4. Exporting filtered datasets based on player skill level
5. Formatting prompts according to the PokerGPT paper specifications

### Data Fields

- `hand_id` (string): Unique identifier for the hand
- `pokergpt_format` (json): Complete structured representation of the hand
  - `basic_info`: General information about the game and players
  - `stages`: Actions and cards for each stage of the hand (preflop, flop, turn, river)
  - `outcomes`: Winner and amount won
- `winner` (string): Player who won the hand
- `bb_won` (float): Amount won in big blinds
- `game_type` (string): Type of poker game
- `big_blind` (float): Size of the big blind
"""

        # Add PokerGPT-specific data fields if relevant
        if pokergpt_format:
            dataset_card += """
- `pokergpt_prompt` (string): Formatted prompt for language model training
- `action` (string, optional): The winning action for supervised training
"""

        dataset_card += f"""
### Dataset Creation Date

{current_date}

### Considerations for Using the Data

This dataset is intended for research and training of poker AI systems. The data has been filtered to include hands from winning players, which may introduce selection bias but is designed to ensure high-quality play samples for training.
"""
        return dataset_card
    
    def export_dataset(self, 
                      filter_query: str, 
                      dataset_name: str, 
                      push_to_hub: bool = False, 
                      hub_name: str = None, 
                      private: bool = True,
                      filter_description: str = "",
                      win_rate_threshold: Optional[float] = None,
                      min_hands: Optional[int] = None,
                      game_stage: Optional[str] = None,
                      include_pokergpt_format: bool = True,
                      include_actions: bool = True):
        """
        Export a filtered dataset to HuggingFace format.
        
        Args:
            filter_query: SQL WHERE clause for filtering hands
            dataset_name: Name for the dataset
            push_to_hub: Whether to push to HuggingFace Hub
            hub_name: HuggingFace Hub repository name
            private: Whether the dataset should be private on HF Hub
            filter_description: Description of filtering criteria
            win_rate_threshold: Minimum win rate for player inclusion
            min_hands: Minimum hands played for player inclusion
            game_stage: Game stage filter (e.g., 'preflop')
            include_pokergpt_format: Whether to include PokerGPT format prompts
            include_actions: Whether to include winning actions
            
        Returns:
            The created HuggingFace Dataset
        """
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
        
        # Generate PokerGPT format prompts for each hand if requested
        if include_pokergpt_format:
            print(f"Generating PokerGPT format prompts for {len(df)} hands...")
            
            # Process in batches to avoid memory issues with large datasets
            batch_size = 1000
            all_prompts = []
            
            for i in range(0, len(df), batch_size):
                batch = df.iloc[i:i+batch_size]
                
                # Format prompts for this batch
                batch_data = []
                for _, row in batch.iterrows():
                    hand_data = {
                        'pokergpt_format': row['pokergpt_format'], 
                        'winner': row['winner']
                    }
                    batch_data.append(hand_data)
                
                # Format the batch using the formatter
                formatted_batch = self.formatter.format_batch_for_training(
                    batch_data, 
                    include_actions=include_actions
                )
                
                # Extract prompts and actions
                for j, item in enumerate(formatted_batch):
                    idx = i + j
                    if idx < len(df):
                        all_prompts.append(item)
                
                print(f"Processed {min(i+batch_size, len(df))}/{len(df)} hands")
            
            # Add prompts and actions to the DataFrame
            df['pokergpt_prompt'] = [item.get('prompt', '') for item in all_prompts]
            
            if include_actions:
                df['action'] = [item.get('action', '') for item in all_prompts]
                # Filter out rows with no action if specifically requested
                if include_actions:
                    df = df.dropna(subset=['action'])
                    print(f"Filtered to {len(df)} hands with valid actions")
        
        # Create the dataset
        dataset = Dataset.from_pandas(df)
        
        # Save dataset card if pushing to hub
        if push_to_hub and hub_name:
            # Create dataset card
            card_content = self._create_dataset_card(
                dataset_name=dataset_name,
                filter_description=filter_description,
                sample_count=len(dataset),
                win_rate_threshold=win_rate_threshold,
                min_hands=min_hands,
                game_stage=game_stage,
                pokergpt_format=include_pokergpt_format
            )
            
            # Save card locally (temporarily)
            card_path = f"{dataset_name}_README.md"
            with open(card_path, "w") as f:
                f.write(card_content)
            
            # Push to HuggingFace Hub with dataset card
            token = os.environ.get("HUGGINGFACE_TOKEN")
            if token:
                dataset.push_to_hub(
                    hub_name, 
                    private=private,
                    readme_path=card_path,
                    token=token
                )
                print(f"Dataset pushed to HuggingFace Hub: {hub_name} (Private: {private})")
            else:
                print("Warning: HUGGINGFACE_TOKEN not found in environment. Set it in .env file.")
                
            # Clean up temporary card file
            os.remove(card_path)
        else:
            # Save locally
            dataset.save_to_disk(dataset_name)
            print(f"Dataset saved locally to: {dataset_name}")
        
        return dataset
    
    def export_winning_player_dataset(self, 
                                     min_win_rate: float = 500, 
                                     min_hands: int = 100, 
                                     dataset_name: str = "winning_players",
                                     push_to_hub: bool = False,
                                     hub_name: str = None,
                                     private: bool = True,
                                     include_pokergpt_format: bool = True):
        """
        Export a dataset filtered to only include hands from winning players.
        
        Args:
            min_win_rate: Minimum player win rate in mbb/h
            min_hands: Minimum hands played by a player
            dataset_name: Name for the dataset
            push_to_hub: Whether to push to HuggingFace Hub
            hub_name: HuggingFace Hub repository name
            private: Whether the dataset should be private on HF Hub
            include_pokergpt_format: Whether to include PokerGPT format prompts
            
        Returns:
            The created HuggingFace Dataset
        """
        filter_query = f"""
            EXISTS (
                SELECT 1 FROM players p
                WHERE 
                    p.player_id = winner
                    AND p.mbb_per_hour >= {min_win_rate}
                    AND p.total_hands >= {min_hands}
            )
        """
        
        filter_description = f"""
This dataset contains hands where the winner has demonstrated a win rate of at least {min_win_rate} mbb/hour over a minimum of {min_hands} hands. 
The table-based win rate calculation approach ensures accurate evaluation of player skill by:

1. Identifying distinct table sessions
2. Detecting when players leave and rejoin tables
3. Creating a timeline of active play that accounts for multi-tabling
4. Calculating win rates based on actual active playing time
        """
        
        return self.export_dataset(
            filter_query=filter_query, 
            dataset_name=dataset_name,
            push_to_hub=push_to_hub,
            hub_name=hub_name,
            private=private,
            filter_description=filter_description,
            win_rate_threshold=min_win_rate,
            min_hands=min_hands,
            include_pokergpt_format=include_pokergpt_format
        )
    
    def export_preflop_dataset(self, 
                              min_win_rate: float = 500, 
                              dataset_name: str = "preflop_decisions",
                              push_to_hub: bool = False,
                              hub_name: str = None,
                              private: bool = True,
                              include_pokergpt_format: bool = True):
        """
        Export a dataset focused on preflop decisions by winning players.
        
        Args:
            min_win_rate: Minimum player win rate in mbb/h
            dataset_name: Name for the dataset
            push_to_hub: Whether to push to HuggingFace Hub
            hub_name: HuggingFace Hub repository name
            private: Whether the dataset should be private on HF Hub
            include_pokergpt_format: Whether to include PokerGPT format prompts
            
        Returns:
            The created HuggingFace Dataset
        """
        filter_query = f"""
            has_preflop = TRUE
            AND EXISTS (
                SELECT 1 FROM players p
                WHERE 
                    p.player_id = ANY(player_ids)
                    AND p.mbb_per_hour >= {min_win_rate}
            )
        """
        
        filter_description = f"""
This dataset focuses specifically on preflop decision-making by skilled poker players. It contains only hands that have preflop actions and where at least one player has demonstrated a win rate of at least {min_win_rate} mbb/hour. This focus makes the dataset particularly useful for training models on the critical initial betting round in poker.
        """
        
        return self.export_dataset(
            filter_query=filter_query, 
            dataset_name=dataset_name,
            push_to_hub=push_to_hub,
            hub_name=hub_name,
            private=private,
            filter_description=filter_description,
            win_rate_threshold=min_win_rate,
            game_stage="preflop",
            include_pokergpt_format=include_pokergpt_format
        )


def main():
    """CLI entry point for the exporter"""
    parser = argparse.ArgumentParser(description='Export poker data to HuggingFace dataset')
    parser.add_argument('--db-connection', required=True, help='Database connection string')
    parser.add_argument('--min-win-rate', type=float, default=500, help='Minimum player win rate in mbb/h')
    parser.add_argument('--min-hands', type=int, default=100, help='Minimum hands played by a player')
    parser.add_argument('--dataset-name', default='winning_players', help='Local dataset name')
    parser.add_argument('--push-to-hub', action='store_true', help='Push to HuggingFace hub')
    parser.add_argument('--hub-name', help='HuggingFace hub dataset name (username/dataset)')
    parser.add_argument('--private', action='store_true', default=True, help='Make dataset private on HuggingFace Hub')
    parser.add_argument('--public', dest='private', action='store_false', help='Make dataset public on HuggingFace Hub')
    parser.add_argument('--preflop-only', action='store_true', help='Export only preflop decisions')
    parser.add_argument('--pokergpt-format', action='store_true', default=True, help='Include PokerGPT format prompts')
    parser.add_argument('--no-pokergpt-format', dest='pokergpt_format', action='store_false', help='Exclude PokerGPT format prompts')
    parser.add_argument('--include-actions', action='store_true', default=True, help='Include winning actions for training')
    parser.add_argument('--no-actions', dest='include_actions', action='store_false', help='Exclude winning actions')
    
    args = parser.parse_args()
    
    exporter = HuggingFaceExporter(args.db_connection)
    
    if args.preflop_only:
        dataset = exporter.export_preflop_dataset(
            min_win_rate=args.min_win_rate,
            dataset_name=args.dataset_name,
            push_to_hub=args.push_to_hub,
            hub_name=args.hub_name,
            private=args.private,
            include_pokergpt_format=args.pokergpt_format
        )
    else:
        dataset = exporter.export_winning_player_dataset(
            min_win_rate=args.min_win_rate,
            min_hands=args.min_hands,
            dataset_name=args.dataset_name,
            push_to_hub=args.push_to_hub,
            hub_name=args.hub_name,
            private=args.private,
            include_pokergpt_format=args.pokergpt_format
        )
    
    print(f"Exported {len(dataset)} hands to dataset")
    
    if args.push_to_hub and not args.hub_name:
        print("Warning: --push-to-hub requires --hub-name to be specified")
        
    # Print a sample if available
    if len(dataset) > 0 and args.pokergpt_format:
        print("\nSample PokerGPT prompt:")
        print("------------------------")
        print(dataset[0]['pokergpt_prompt'])


if __name__ == "__main__":
    main()