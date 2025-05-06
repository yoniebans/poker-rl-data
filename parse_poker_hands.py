# data_wrangler/parse_poker_hands.py
import json
import psycopg2
from typing import Dict, List, Tuple, Any
import re
import argparse

class PokerHandProcessor:
    def __init__(self, db_connection_string: str):
        self.conn = psycopg2.connect(db_connection_string)
        self.conn.autocommit = True
        
    def parse_pokerstars_hand(self, raw_hand: str) -> Dict[str, Any]:
        """Parse a PokerStars hand history into structured format"""
        # Extract hand ID
        hand_id_match = re.search(r'Hand #(\d+)', raw_hand)
        if not hand_id_match:
            raise ValueError("Could not find hand ID in the hand history")
        hand_id = hand_id_match.group(1)
        
        # Extract game type and blinds with improved regex
        game_info_match = re.search(r':\s+([\w\' ]+)\s+\((\$[\d.]+/\$[\d.]+)', raw_hand)
        if not game_info_match:
            raise ValueError("Could not parse game type and blinds from hand history")
        
        game_type = game_info_match.group(1).strip()  # e.g., "Hold'em No Limit"
        blinds_str = game_info_match.group(2)  # e.g., "$0.50/$1.00"
        
        # Extract just the numeric blind values
        blinds_match = re.search(r'\$([\d.]+)/\$([\d.]+)', blinds_str)
        if not blinds_match:
            raise ValueError("Could not parse blind values")
        
        blinds = [float(blinds_match.group(1)), float(blinds_match.group(2))]
        
        # Extract players and their stacks - improved to handle more username formats
        players = {}
        for player_match in re.finditer(r'Seat (\d+): (\S+) \(\$?([\d.]+)', raw_hand):
            seat, player_name, stack = player_match.groups()
            players[player_name] = {
                'seat': int(seat),
                'stack': float(stack)
            }
        
        # Extract winner and amount won - improved to handle more username formats
        winner = None
        bb_won = 0
        winner_match = re.search(r'(\S+) collected \$?([\d.]+)', raw_hand)
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
        # Parse player actions from a stage - improved to handle more username formats
        actions = []
        for action_match in re.finditer(r'(\S+): (calls|bets|raises|folds|checks)(?: \$?([\d.]+)(?: to \$?([\d.]+))?)?', stage_text):
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
        try:
            # Start a transaction explicitly
            with self.conn:  # This creates a transaction context
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
            # Transaction is automatically committed if successful
            # or rolled back if an exception occurs
            print(f"Successfully inserted hand {parsed_hand['hand_id']}")
            return True
        except Exception as e:
            # Transaction is already rolled back by the context manager
            print(f"Error inserting hand {parsed_hand.get('hand_id', 'unknown')}: {e}")
            return False
    
    def process_hand_file(self, file_path):
        """Process a file containing multiple hand histories with robust error handling"""
        # First try reading with UTF-8 and handle specific errors
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError as e:
            # Get info about where the error occurred
            print(f"Decode error at position {e.start} in file {file_path}")
            
            # Read the file in binary mode
            with open(file_path, 'rb') as f:
                raw_data = f.read()
            
            # Implement a hybrid approach - read as UTF-8 but replace problematic characters
            content = raw_data.decode('utf-8', errors='replace')
            print(f"Continuing with replaced characters in file {file_path}")
            
            # Optionally log files with encoding issues for review
            with open('encoding_issues.log', 'a') as log:
                log.write(f"{file_path}: {str(e)}\n")
        
        # Process hand histories as before
        hand_splits = re.split(r'(?=PokerStars Hand #)', content)
        
        hands_processed = 0
        hands_failed = 0
        
        for hand_text in hand_splits:
            if not hand_text.strip():
                continue
                
            try:
                parsed_hand = self.parse_pokerstars_hand(hand_text)
                self.insert_hand(parsed_hand)
                hands_processed += 1
                if hands_processed % 100 == 0:
                    print(f"Processed {hands_processed} hands from {file_path}")
            except Exception as e:
                hands_failed += 1
                print(f"Error processing hand: {e}")
                continue
        
        print(f"File {file_path} complete: {hands_processed} hands processed, {hands_failed} failed")
    
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