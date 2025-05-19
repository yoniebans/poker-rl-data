# Poker RL Data Processing Pipeline

This project creates a data processing pipeline for poker hand histories, focused on creating high-quality training datasets for reinforcement learning models.

## Project Components

```ascii
┌───────────────┐     ┌────────────────┐     ┌──────────────┐     ┌───────────────┐
│ Hand History  │     │ PostgreSQL DB  │     │ PokerGPT     │     │ HuggingFace   │
│ Parser        │────>│ Storage        │────>│ Formatter    │────>│ Dataset       │
└───────────────┘     └────────────────┘     └──────────────┘     └───────────────┘
                             │
                             ▼
                      ┌────────────────┐
                      │ Win Rate       │
                      │ Calculator     │
                      └────────────────┘
```

## Database Schema

```sql
CREATE TABLE hand_histories (
    hand_id TEXT PRIMARY KEY,
    raw_text TEXT,
    pokergpt_format JSONB,
    
    -- Metadata for filtering
    game_type TEXT,
    blinds NUMERIC[2],
    big_blind NUMERIC,
    player_count INTEGER,
    
    -- Win statistics
    winner TEXT,
    bb_won NUMERIC,
    
    -- Game states
    has_preflop BOOLEAN,
    has_flop BOOLEAN,
    has_turn BOOLEAN, 
    has_river BOOLEAN,
    has_showdown BOOLEAN,
    
    -- Player filtering
    player_ids TEXT[],
    player_win_rates JSONB,  -- Map of player_id -> win_rate (mbb/h)
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index for filtering by win rates
CREATE INDEX idx_player_win_rates ON hand_histories USING GIN (player_win_rates);
```

## Processing Scripts

### A. Poker Hand Parser and DB Inserter

```python
# scripts/parse_poker_hands.py
import json
import psycopg2
from typing import Dict, List, Tuple, Any
import re
import argparse

class PokerHandProcessor:
    def __init__(self, db_connection_string: str):
        self.conn = psycopg2.connect(db_connection_string)
        
    def parse_hand(self, raw_hand: str) -> Dict[str, Any]:
        """Parse hand history into structured format"""
        # Extract hand ID
        hand_id = re.search(r'Hand #(\d+)', raw_hand).group(1)
        
        # Extract game type and blinds
        game_info = re.search(r'(\$[\d.]+/\$[\d.]+) ([^(]+)', raw_hand)
        blinds_str = game_info.group(1)
        game_type = game_info.group(2).strip()
        blinds = [float(x.replace('$', '')) for x in blinds_str.split('/')]
        
        # Extract players and their stacks
        players = {}
        for player_match in re.finditer(r'Seat (\d+): (\w+) \(\$?([\d.]+)', raw_hand):
            seat, player_name, stack = player_match.groups()
            players[player_name] = {
                'seat': int(seat),
                'stack': float(stack)
            }
        
        # Extract winner and amount won
        winner = None
        bb_won = 0
        winner_match = re.search(r'(\w+) collected \$?([\d.]+)', raw_hand)
        if winner_match:
            winner = winner_match.group(1)
            amount_won = float(winner_match.group(2))
            bb_won = amount_won / blinds[1]  # Convert to big blinds
        
        # Determine game stages
        has_preflop = "*** HOLE CARDS ***" in raw_hand
        has_flop = "*** FLOP ***" in raw_hand
        has_turn = "*** TURN ***" in raw_hand
        has_river = "*** RIVER ***" in raw_hand
        has_showdown = "*** SHOW DOWN ***" in raw_hand
        
        # Convert to PokerGPT format
        pokergpt_format = self._convert_to_pokergpt_format(
            raw_hand, players, blinds, winner, bb_won
        )
        
        return {
            'hand_id': hand_id,
            'raw_text': raw_hand,
            'pokergpt_format': pokergpt_format,
            'game_type': game_type,
            'blinds': blinds,
            'big_blind': blinds[1],
            'player_count': len(players),
            'winner': winner,
            'bb_won': bb_won,
            'has_preflop': has_preflop,
            'has_flop': has_flop,
            'has_turn': has_turn,
            'has_river': has_river,
            'has_showdown': has_showdown,
            'player_ids': list(players.keys()),
            'player_win_rates': {}  # Will be updated in a separate process
        }
    
    def _convert_to_pokergpt_format(self, raw_hand, players, blinds, winner, bb_won):
        """Convert parsed hand to PokerGPT format"""
        # This needs to match the specific format used by PokerGPT
        return {
            "basic_info": {
                "blinds": f"{blinds[0]}/{blinds[1]}",
                "players": [{"name": name, "stack": data["stack"]} for name, data in players.items()],
                "dealer_position": self._extract_dealer_position(raw_hand)
            },
            "stages": self._extract_stages(raw_hand),
            "outcomes": {
                "winner": winner,
                "bb_won": bb_won
            }
        }
    
    def _extract_dealer_position(self, raw_hand):
        # Extract dealer position
        dealer_match = re.search(r'Seat #(\d+) is the button', raw_hand)
        if dealer_match:
            return int(dealer_match.group(1))
        return None
    
    def _extract_stages(self, raw_hand):
        # Extract information for each stage (preflop, flop, turn, river)
        stages = {}
        
        # Define stage markers in the hand history
        stage_markers = [
            ("preflop", "*** HOLE CARDS ***", "*** FLOP ***"),
            ("flop", "*** FLOP ***", "*** TURN ***"),
            ("turn", "*** TURN ***", "*** RIVER ***"),
            ("river", "*** RIVER ***", "*** SHOW DOWN ***")
        ]
        
        for stage_name, start_marker, end_marker in stage_markers:
            if start_marker in raw_hand:
                start_idx = raw_hand.index(start_marker) + len(start_marker)
                end_idx = raw_hand.index(end_marker) if end_marker in raw_hand else len(raw_hand)
                stage_text = raw_hand[start_idx:end_idx].strip()
                
                # Parse actions for this stage
                actions = self._parse_actions(stage_text)
                
                # For flop/turn/river, also extract community cards
                cards = None
                if stage_name != "preflop":
                    cards = self._extract_community_cards(stage_text, stage_name)
                
                stages[stage_name] = {
                    "actions": actions,
                    "community_cards": cards
                }
        
        return stages
    
    def _parse_actions(self, stage_text):
        # Parse player actions from a stage
        actions = []
        for action_match in re.finditer(r'(\w+): (calls|bets|raises|folds|checks)(?: \$?([\d.]+)(?: to \$?([\d.]+))?)?', stage_text):
            player, action, amount, total = action_match.groups()
            
            action_data = {
                "player": player,
                "action": action
            }
            
            if amount:
                action_data["amount"] = float(amount)
            if total:
                action_data["total"] = float(total)
                
            actions.append(action_data)
            
        return actions
    
    def _extract_community_cards(self, stage_text, stage_name):
        # Extract community cards based on the stage
        card_pattern = r'\[(.*?)\]'
        if stage_name == "flop":
            # Flop has 3 cards
            match = re.search(card_pattern, stage_text)
            if match:
                return match.group(1).split()
        elif stage_name == "turn" or stage_name == "river":
            # Turn and river add 1 card
            match = re.search(card_pattern, stage_text)
            if match:
                return match.group(1).split()[-1]
        return None
    
    def insert_hand(self, parsed_hand):
        """Insert a parsed hand into the database"""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO hand_histories (
                    hand_id, raw_text, pokergpt_format, game_type, blinds, big_blind,
                    player_count, winner, bb_won, has_preflop, has_flop, has_turn,
                    has_river, has_showdown, player_ids
                ) VALUES (
                    %(hand_id)s, %(raw_text)s, %(pokergpt_format)s, %(game_type)s, %(blinds)s, %(big_blind)s,
                    %(player_count)s, %(winner)s, %(bb_won)s, %(has_preflop)s, %(has_flop)s, %(has_turn)s,
                    %(has_river)s, %(has_showdown)s, %(player_ids)s
                )
            """, {
                **parsed_hand,
                'pokergpt_format': json.dumps(parsed_hand['pokergpt_format']),
                'blinds': parsed_hand['blinds']
            })
        self.conn.commit()
    
    def process_hand_file(self, file_path):
        """Process a file containing multiple hand histories"""
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Split the file into individual hands
        # Hand histories typically start with "Ref Hand #"
        hand_splits = re.split(r'(?=PokerStars Hand #)', content)
        
        for hand_text in hand_splits:
            if not hand_text.strip():
                continue
                
            try:
                parsed_hand = self.parse_hand(hand_text)
                self.insert_hand(parsed_hand)
                print(f"Processed hand {parsed_hand['hand_id']}")
            except Exception as e:
                print(f"Error processing hand: {e}")
                continue
    
    def close(self):
        """Close the database connection"""
        self.conn.close()

def main():
    parser = argparse.ArgumentParser(description='Parse poker hand histories and store in database')
    parser.add_argument('--input-dir', required=True, help='Directory containing hand history files')
    parser.add_argument('--db-connection', required=True, help='Database connection string')
    
    args = parser.parse_args()
    
    import os
    processor = PokerHandProcessor(args.db_connection)
    
    # Process each file in the input directory
    for filename in os.listdir(args.input_dir):
        if filename.endswith('.txt'):
            file_path = os.path.join(args.input_dir, filename)
            print(f"Processing file: {file_path}")
            processor.process_hand_file(file_path)
    
    processor.close()
    print("Processing complete")

if __name__ == "__main__":
    main()
```

### B. Player Win Rate Calculator

```python
# scripts/calculate_win_rates.py
import json
import psycopg2
import argparse

class PlayerWinRateCalculator:
    def __init__(self, db_connection_string: str):
        self.conn = psycopg2.connect(db_connection_string)
    
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
                
            # Calculate mbb/h (milli-big blinds per hour)
            mbb_per_hand = (total_bb * 1000) / total_hands
            hands_per_hour = 30  # Assumption: average hands per hour
            mbb_per_hour = mbb_per_hand * hands_per_hour
            
            player_win_rates[player_id] = {
                'total_hands': total_hands,
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
                    json.dumps({player_id: stats}),
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
```

### C. HuggingFace Dataset Exporter

```python
# scripts/export_to_hf.py
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
```

## Custom Reward Functions

### Reward Functions Module Initialization

```python
# reward_fns/__init__.py
from atroposlib.envs.reward_fns import registry

# Import to register the reward functions
from .action_match import PokerActionMatchReward
from .bet_sizing import PokerBetSizingReward
from .combined_poker import CombinedPokerReward

__all__ = [
    "PokerActionMatchReward",
    "PokerBetSizingReward", 
    "CombinedPokerReward"
]
```

### Action Match Reward

```python
# reward_fns/action_match.py
from typing import Any, List, Optional
import re
from atroposlib.envs.reward_fns import registry, RewardFunction

@registry.register
class PokerActionMatchReward(RewardFunction):
    """Reward function that scores based on match to winning player's action"""
    
    def __init__(
        self,
        exact_match_score: float = 1.0,
        action_type_score: float = 0.7,
        related_action_score: float = 0.5,
        weight: float = 1.0,
        **kwargs
    ):
        super().__init__(weight=weight, **kwargs)
        self.exact_match_score = exact_match_score
        self.action_type_score = action_type_score
        self.related_action_score = related_action_score
    
    def compute(self, completions: List[Any], winner_action: Optional[str] = None, **kwargs) -> List[float]:
        """Score completions based on similarity to winner's action"""
        if winner_action is None:
            return [0.0] * len(completions)
            
        scores = []
        for completion in completions:
            content = self.get_content(completion)
            scores.append(self._score_single_response(content, winner_action))
        
        return scores
    
    def _score_single_response(self, response: str, winner_action: str) -> float:
        """Score a single response based on similarity to winner's action"""
        if winner_action is None:
            return 0.0  # No winner action to compare against
        
        # Extract action type and amount if present
        winner_parts = winner_action.lower().split()
        winner_action_type = winner_parts[0]
        winner_amount = float(winner_parts[1]) if len(winner_parts) > 1 else None
        
        # Look for action keywords in response
        response = response.lower()
        
        # Check for exact action match
        if winner_action_type in response:
            # Perfect match on action type
            if winner_amount is None:
                return self.exact_match_score  # Full points for matching action with no amount
            
            # Look for amount in response
            amount_matches = re.findall(r'(\d+(?:\.\d+)?)', response)
            if amount_matches:
                response_amount = float(amount_matches[0])
                # Score based on how close the amount is
                amount_ratio = min(response_amount, winner_amount) / max(response_amount, winner_amount)
                return self.action_type_score + ((self.exact_match_score - self.action_type_score) * amount_ratio)
            
            return self.action_type_score  # Matched action but no amount
        
        # Check for related actions (partial credit)
        aggressive_actions = ["bet", "raise"]
        passive_actions = ["check", "call"]
        fold_action = "fold"
        
        if winner_action_type in aggressive_actions and any(a in response for a in aggressive_actions):
            return self.related_action_score  # Partial credit for similar aggressive action
        elif winner_action_type in passive_actions and any(a in response for a in passive_actions):
            return self.related_action_score  # Partial credit for similar passive action
        elif winner_action_type == fold_action and fold_action in response:
            return self.exact_match_score  # Full credit for fold (binary decision)
        
        return 0.0  # No match
```

### Bet Sizing Reward

```python
# reward_fns/bet_sizing.py
from typing import Any, List, Optional
import re
from atroposlib.envs.reward_fns import registry, RewardFunction

@registry.register
class PokerBetSizingReward(RewardFunction):
    """Reward function specifically for evaluating bet sizing accuracy"""
    
    def __init__(
        self,
        perfect_match_score: float = 1.0,
        min_score: float = 0.0,
        max_deviation_pct: float = 0.5,  # Max deviation for non-zero score
        weight: float = 1.0,
        **kwargs
    ):
        super().__init__(weight=weight, **kwargs)
        self.perfect_match_score = perfect_match_score
        self.min_score = min_score
        self.max_deviation_pct = max_deviation_pct
    
    def compute(self, completions: List[Any], winner_action: Optional[str] = None, **kwargs) -> List[float]:
        """Score bet sizing accuracy compared to winner's action"""
        if winner_action is None:
            return [0.0] * len(completions)
            
        # Extract winner bet amount if present
        winner_parts = winner_action.lower().split()
        if len(winner_parts) < 2 or winner_parts[0] not in ["bet", "raise"]:
            return [0.0] * len(completions)  # Not a betting action
            
        try:
            winner_amount = float(winner_parts[1])
        except (ValueError, IndexError):
            return [0.0] * len(completions)  # Invalid amount format
        
        scores = []
        for completion in completions:
            content = self.get_content(completion).lower()
            
            # Check if it's a betting action
            if "bet" not in content and "raise" not in content:
                scores.append(0.0)
                continue
                
            # Extract amount
            amount_matches = re.findall(r'(\d+(?:\.\d+)?)', content)
            if not amount_matches:
                scores.append(0.0)
                continue
                
            response_amount = float(amount_matches[0])
            
            # Calculate deviation
            max_amount = max(response_amount, winner_amount)
            min_amount = min(response_amount, winner_amount)
            
            if min_amount == 0:
                deviation = 1.0  # Maximum deviation
            else:
                deviation = (max_amount - min_amount) / min_amount
            
            # Score based on deviation
            if deviation > self.max_deviation_pct:
                score = self.min_score
            else:
                # Linear interpolation between perfect and min score
                score = self.perfect_match_score - (deviation / self.max_deviation_pct) * (self.perfect_match_score - self.min_score)
                
            scores.append(score)
        
        return scores
```

### Combined Poker Reward

```python
# reward_fns/combined_poker.py
from typing import List, Dict, Any
from atroposlib.envs.reward_fns import registry, CombinedReward

@registry.register
class CombinedPokerReward(CombinedReward):
    """Pre-configured combined reward for poker action evaluation"""
    
    def __init__(self, 
                 action_weight: float = 0.6,
                 sizing_weight: float = 0.4,
                 normalization: str = "sum",
                 weight: float = 1.0,
                 **kwargs):
        
        rewards = [
            {"type": "poker_action_match", "weight": action_weight},
            {"type": "poker_bet_sizing", "weight": sizing_weight}
        ]
        
        super().__init__(
            rewards=rewards,
            normalization=normalization,
            weight=weight,
            **kwargs
        )
```

## Poker Environment Implementation

```python
# environments/poker_env.py
import sys
import os
import random
import asyncio
from typing import Any, Dict, List, Tuple, Optional, Union
from datasets import load_from_disk
from transformers import AutoTokenizer

from atroposlib.envs.base import BaseEnv, ScoredDataGroup, BaseEnvConfig

# Add the parent directory to the path to find reward_fns
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import custom reward functions to ensure they're registered
from reward_fns import PokerActionMatchReward, PokerBetSizingReward, CombinedPokerReward

class PokerEnvConfig(BaseEnvConfig):
    """Configuration for the Poker environment"""
    dataset_path: str = "winning_players"
    reward_action_weight: float = 0.7
    reward_sizing_weight: float = 0.3
    
class PokerEnv(BaseEnv):
    """Poker training environment using processed hand histories"""
    
    name = "poker_env"
    env_config_cls = PokerEnvConfig
    
    async def setup(self):
        """Load the dataset and prepare environment"""
        # Load dataset
        self.dataset = load_from_disk(self.config.dataset_path)
        self.tokenizer = AutoTokenizer.from_pretrained(self.config.tokenizer_name)
        
        # Initialize reward function
        from atroposlib.envs.reward_fns import registry
        self.reward_function = registry.create(
            "combined_poker", 
            action_weight=self.config.reward_action_weight,
            sizing_weight=self.config.reward_sizing_weight
        )
        
        # Group hands by game stage for easier access
        self.preflop_hands = [i for i, item in enumerate(self.dataset) if "preflop" in item["pokergpt_format"]["stages"]]
        self.flop_hands = [i for i, item in enumerate(self.dataset) if "flop" in item["pokergpt_format"]["stages"]]
        self.turn_hands = [i for i, item in enumerate(self.dataset) if "turn" in item["pokergpt_format"]["stages"]]
        self.river_hands = [i for i, item in enumerate(self.dataset) if "river" in item["pokergpt_format"]["stages"]]
        
        print(f"Loaded dataset with {len(self.dataset)} hands")
        print(f"  Preflop: {len(self.preflop_hands)}")
        print(f"  Flop: {len(self.flop_hands)}")
        print(f"  Turn: {len(self.turn_hands)}")
        print(f"  River: {len(self.river_hands)}")
    
    async def get_next_item(self) -> Dict:
        """Get a random hand from the dataset"""
        # Select a random stage to train on
        stages = ["preflop", "flop", "turn", "river"]
        stage = random.choice(stages)
        
        # Get a hand from the selected stage
        if stage == "preflop" and self.preflop_hands:
            idx = random.choice(self.preflop_hands)
        elif stage == "flop" and self.flop_hands:
            idx = random.choice(self.flop_hands)
        elif stage == "turn" and self.turn_hands:
            idx = random.choice(self.turn_hands)
        elif stage == "river" and self.river_hands:
            idx = random.choice(self.river_hands)
        else:
            # Fallback to any random hand
            idx = random.randint(0, len(self.dataset) - 1)
        
        hand = self.dataset[idx]
        
        # Format hand as a poker situation
        situation = self.format_poker_situation(hand, stage)
        
        return {
            "hand_id": hand["hand_id"],
            "situation": situation,
            "winner_action": self.extract_winner_action(hand, stage),
            "bb_won": hand["bb_won"],
            "stage": stage
        }
    
    def format_poker_situation(self, hand: Dict, stage: str) -> str:
        """Format a hand into a prompt for the LLM"""
        # This should match the format used for PokerGPT
        pokergpt_format = hand["pokergpt_format"]
        
        # Format basic game info
        game_info = (
            f"Player's number: {len(pokergpt_format['basic_info']['players'])}\n"
            f"Dealer's position: {pokergpt_format['basic_info']['dealer_position']}\n"
            f"Blinds: {pokergpt_format['basic_info']['blinds']}\n"
        )
        
        # Format player stacks
        player_info = ""
        for i, player in enumerate(pokergpt_format['basic_info']['players']):
            player_info += f"Player {i+1}: {player['name']}, stack: {player['stack']}\n"
        
        # Format actions for previous stages
        previous_actions = ""
        stages_order = ["preflop", "flop", "turn", "river"]
        current_stage_index = stages_order.index(stage)
        
        for prev_stage in stages_order[:current_stage_index]:
            if prev_stage in pokergpt_format["stages"]:
                previous_actions += f"{prev_stage.upper()} actions:\n"
                for action in pokergpt_format["stages"][prev_stage]["actions"]:
                    action_str = f"{action['player']}: {action['action']}"
                    if "amount" in action:
                        action_str += f" {action['amount']}"
                    previous_actions += f"{action_str};\n"
        
        # Format current stage - show the cards but not the actions
        current_stage = ""
        if stage != "preflop":
            current_stage += f"{stage.upper()} cards: "
            if "community_cards" in pokergpt_format["stages"][stage]:
                current_stage += f"{pokergpt_format['stages'][stage]['community_cards']}\n"
        
        # Combine all parts into the final prompt
        prompt = (
            f"You are an experienced poker player. I need your help deciding what to do in this situation:\n\n"
            f"{game_info}\n"
            f"{player_info}\n"
            f"{previous_actions}\n"
            f"{current_stage}\n"
            f"What action should I take as the next player to act? Choose from: fold, check, call, bet, or raise."
        )
        
        return prompt
    
    def extract_winner_action(self, hand: Dict, stage: str) -> str:
        """Extract the action taken by the winning player in this stage"""
        winner = hand["winner"]
        pokergpt_format = hand["pokergpt_format"]
        
        if stage not in pokergpt_format["stages"]:
            return None  # Winner might not have acted in this stage
        
        # Find the action taken by the winner
        for action in pokergpt_format["stages"][stage]["actions"]:
            if action["player"] == winner:
                action_str = action["action"]
                if "amount" in action:
                    action_str += f" {action['amount']}"
                return action_str
        
        return None
    
    async def collect_trajectory(self, item: Dict) -> Tuple[Any | None, List[Dict]]:
        """Get and score a single response from the model"""
        situation = item["situation"]
        
        # Get model response
        response = await self.server.chat_completion(
            messages=[{"role": "user", "content": situation}],
            temperature=0.7,
            max_tokens=50
        )
        
        text = response.choices[0].message.content.strip()
        
        # Score using reward function
        scores = self.reward_function.compute([text], winner_action=item["winner_action"])
        score = scores[0] if scores else 0.0
        
        # Tokenize the response
        tokens = self.tokenizer.encode(text)
        masks = [-100] * len(tokens)  # Standard masking - adjust if needed
        
        # Create scored data
        scored_data = {
            "tokens": [tokens],
            "masks": [masks],
            "scores": [score],
            "messages": [[{"role": "user", "content": situation}, 
                         {"role": "assistant", "content": text}]]
        }
        
        return scored_data, []  # No backlog items
    
    async def evaluate(self, *args, **kwargs):
        """Evaluate the current model on a held-out set of poker situations"""
        # Simple evaluation against held-out data
        eval_accuracies = []
        eval_scores = []
        
        # Create evaluation tasks
        eval_tasks = []
        for _ in range(50):  # Evaluate on 50 random situations
            item = await self.get_next_item()
            eval_tasks.append(self.collect_trajectory(item))
        
        # Run evaluation tasks
        results = await asyncio.gather(*eval_tasks)
        
        # Process results
        for result, _ in results:
            if result is not None:
                eval_scores.append(result["scores"][0])
                # Check for "correct" action (score > 0.7)
                eval_accuracies.append(1.0 if result["scores"][0] > 0.7 else 0.0)
        
        # Log metrics
        metrics = {
            "eval/accuracy": sum(eval_accuracies) / len(eval_accuracies) if eval_accuracies else 0,
            "eval/average_score": sum(eval_scores) / len(eval_scores) if eval_scores else 0,
        }
        
        await self.wandb_log(metrics)
```

## Core Components

1. **Hand Parser** (`data_wrangler/parse_poker_hands.py`)
   - Parses hand history files
   - Extracts structured data using robust pattern matching
   - Handles edge cases including multi-table situations

2. **Database Schema**
   - Structured storage with filtering capabilities
   - Support for win rate tracking and advanced queries
   - Efficient hand retrieval for dataset creation

3. **Win Rate Calculator** (`data_wrangler/player_win_rates.py`)
   - Table-based approach for accurate win rate calculation
   - Tracks player performance across multiple tables
   - Creates reliable player metrics for filtering skilled players

4. **PokerGPT Formatter** (`data_wrangler/pokergpt_formatter.py`)
   - Transforms structured hand data into LLM-ready prompt format
   - Handles special cases like all-in situations
   - Maintains consistent formatting and indentation
   - Removes winning player's final action for training purposes

5. **Dataset Exporter** (`data_wrangler/export_to_hf.py`)
   - Filters hands based on player skill level
   - Creates HuggingFace-compatible datasets
   - Supports both local storage and hub publishing

## Current Status

The core data pipeline is operational, with recent improvements to:
- Fix prompt formatting and indentation
- Handle all-in situations correctly
- Calculate pot values accurately
- Generate reference examples for debugging

Next steps include:
- Further refinements to prompt structure
- Integration with RL training environment
- Expanded test coverage for edge cases