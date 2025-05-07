import json
import psycopg2
from typing import Dict, List, Tuple, Any, Optional
import re
import argparse
from datetime import datetime
import os

class PokerHandProcessor:
    def __init__(self, db_connection_string: str, debug_mode: bool = False):
        self.conn = psycopg2.connect(db_connection_string)
        self.conn.autocommit = True
        self.debug_mode = debug_mode
        self.debug_log = []
        
        # Create a diagnostic directory if in debug mode
        if self.debug_mode:
            os.makedirs('diagnostic_logs', exist_ok=True)
        
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
        
        # Extract table name
        table_match = re.search(r"Table '([^']+)'", raw_hand)
        table_name = table_match.group(1) if table_match else None
        
        # Extract timestamp
        timestamp_match = re.search(r'(\d{4}/\d{2}/\d{2} \d{1,2}:\d{2}:\d{2})', raw_hand)
        played_at = None
        if timestamp_match:
            try:
                # Parse the timestamp from the hand history
                timestamp_str = timestamp_match.group(1)
                played_at = datetime.strptime(timestamp_str, '%Y/%m/%d %H:%M:%S')
            except (ValueError, TypeError) as e:            
                raise ValueError(f"Could not parse timestamp from hand {hand_id}: {e}")                
        
        # Extract players and their stacks - only search up to HOLE CARDS section
        players = {}
        # First check if the HOLE CARDS section exists and limit our search area
        hole_cards_index = raw_hand.find("*** HOLE CARDS ***")
        if hole_cards_index != -1:
            # Only search in the text before the HOLE CARDS section
            player_section = raw_hand[:hole_cards_index]
        else:            
            # Abort processing this hand
            raise ValueError(f"Invalid hand data: Missing HOLE CARDS section in hand #{hand_id}")

        # Now extract players only from the truncated section
        for player_match in re.finditer(r'Seat (\d+): (.*?) \(\$?([\d.]+)', player_section):
            seat, player_name, stack = player_match.groups()
            players[player_name] = {
                'seat': int(seat),
                'stack': float(stack)
            }
        
        # Extract dealer position
        dealer_position = self._extract_dealer_position(raw_hand)
        
        # Find the dealer player based on the dealer position
        dealer_player = None
        if dealer_position:
            # Search through players to find who is sitting in the dealer position
            for player_name, player_data in players.items():
                if player_data['seat'] == dealer_position:
                    dealer_player = player_name
                    break
        
        # Extract small and big blind players
        small_blind_player, big_blind_player = self._extract_blind_players(raw_hand)
        
        # Extract all actions to find missing players
        all_actions, missing_action_players = self._extract_all_actions(raw_hand, players, hand_id)
        
        # Save the raw text for hands with missing players
        if missing_action_players and self.debug_mode:
            self._save_problematic_hand(hand_id, raw_hand, players, missing_action_players)
        
        # Extract winner and amount won - improved to handle more username formats
        winner = None
        bb_won = 0
        winner_match = re.search(r'(.*?) collected \$?([\d.]+)', raw_hand)
        if winner_match:
            winner = winner_match.group(1)
            amount_won = float(winner_match.group(2))
            bb_won = amount_won / blinds[1]  # Convert to big blinds
            
            # Check if the winner is in the player list
            if winner not in players and self.debug_mode:
                self.debug_log.append(f"WARNING: Winner '{winner}' not found in player list for hand {hand_id}")
        
        # Determine game stages
        has_preflop = "*** HOLE CARDS ***" in raw_hand
        has_flop = "*** FLOP ***" in raw_hand
        has_turn = "*** TURN ***" in raw_hand
        has_river = "*** RIVER ***" in raw_hand
        has_showdown = "*** SHOW DOWN ***" in raw_hand
        
        # Extract stages including showdown
        stages = self._extract_stages(raw_hand, players, hand_id)
        
        # Extract summary information
        summary_info = self._extract_summary(raw_hand)
        
        # Convert to PokerGPT format
        pokergpt_format = self._convert_to_pokergpt_format(
            raw_hand, players, blinds, winner, bb_won, stages, summary_info,
            small_blind_player, big_blind_player, dealer_position, dealer_player
        )
        
        # Get pot total, rake, and board from summary info
        pot_total = summary_info.get('pot_total') if summary_info else None
        rake = summary_info.get('rake') if summary_info else None
        board = summary_info.get('board') if summary_info else None
        
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
            'played_at': played_at,
            'table_name': table_name,
            'dealer_position': dealer_position,
            'dealer_player': dealer_player,
            'small_blind_player': small_blind_player,
            'big_blind_player': big_blind_player,
            'pot_total': pot_total,
            'rake': rake,
            'board': board
        }
    
    def _extract_blind_players(self, raw_hand: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract the players who posted small and big blinds."""
        small_blind_player = None
        big_blind_player = None
        
        # Look for patterns like "PlayerName: posts small blind $0.50"
        sb_match = re.search(r'(.*?): posts small blind', raw_hand)
        if sb_match:
            small_blind_player = sb_match.group(1).strip()
        
        # Look for patterns like "PlayerName: posts big blind $1"
        bb_match = re.search(r'(.*?): posts big blind', raw_hand)
        if bb_match:
            big_blind_player = bb_match.group(1).strip()
            
        return small_blind_player, big_blind_player
    
    def _save_problematic_hand(self, hand_id, raw_hand, players, missing_players):
        """Save problematic hands to separate files for analysis"""
        filename = f"diagnostic_logs/hand_{hand_id}_missing_players.txt"
        with open(filename, 'w') as f:
            f.write(f"HAND ID: {hand_id}\n")
            f.write("=" * 50 + "\n")
            f.write("MISSING PLAYERS:\n")
            for player in missing_players:
                f.write(f"  - {player}\n")
            f.write("\nKNOWN PLAYERS:\n")
            for player, data in players.items():
                f.write(f"  - {player} (Seat {data['seat']}, Stack {data['stack']})\n")
            f.write("\nRAW HAND TEXT:\n")
            f.write(raw_hand)
        
        self.debug_log.append(f"Saved problematic hand {hand_id} to {filename}")
    
    def _extract_all_actions(self, raw_hand, players, hand_id):
        """Extract all player actions from the hand to check for missing players"""
        all_actions = []
        
        # Use a simpler approach - get lines with player actions
        lines = raw_hand.split('\n')
        action_lines = [line.strip() for line in lines if ': ' in line and any(action in line for action in 
                        [': calls ', ': bets ', ': raises ', ': folds', ': checks'])]
        
        for line in action_lines:
            parts = line.split(': ', 1)
            if len(parts) == 2:
                player_name = parts[0].strip()
                action_text = parts[1].strip()
                
                action_type = None
                if action_text.startswith('calls '):
                    action_type = 'calls'
                elif action_text.startswith('bets '):
                    action_type = 'bets'
                elif action_text.startswith('raises '):
                    action_type = 'raises'
                elif action_text == 'folds':
                    action_type = 'folds'
                elif action_text == 'checks':
                    action_type = 'checks'
                
                if action_type:
                    all_actions.append({'player': player_name, 'action': action_type})
        
        # Check for players in actions that aren't in the player list
        action_players = set(action['player'] for action in all_actions)
        known_players = set(players.keys())
        missing_players = action_players - known_players
        
        if missing_players and self.debug_mode:
            self.debug_log.append(f"DIAGNOSTIC: Hand {hand_id} has {len(missing_players)} players in actions but not in player list:")
            for player in missing_players:
                # Count how many actions this missing player has
                action_count = sum(1 for a in all_actions if a['player'] == player)
                self.debug_log.append(f"  - Missing player: '{player}' appears in {action_count} actions")
                
                # Try to find this player in the raw text
                player_mentions = re.findall(re.escape(player), raw_hand)
                self.debug_log.append(f"    Player name '{player}' appears {len(player_mentions)} times in raw text")
                
                # Find the first few mentions with context
                for i, match in enumerate(re.finditer(re.escape(player), raw_hand)):
                    if i >= 3:  # Limit to first 3 mentions
                        break
                    start = max(0, match.start() - 20)
                    end = min(len(raw_hand), match.end() + 20)
                    context = raw_hand[start:end].replace('\n', ' ')
                    self.debug_log.append(f"    Context {i+1}: ...{context}...")
                    
                # Try to find if this player's name is part of a longer name
                for known_player in known_players:
                    if player in known_player and player != known_player:
                        self.debug_log.append(f"    *** POTENTIAL MATCH: '{player}' might be part of '{known_player}'")
        
        return all_actions, missing_players
    
    def _convert_to_pokergpt_format(self, raw_hand, players, blinds, winner, bb_won, stages=None, summary_info=None, 
                                  small_blind_player=None, big_blind_player=None, dealer_position=None, dealer_player=None):
        """Convert parsed hand to PokerGPT format with enhanced information."""
        # Extract table name
        table_match = re.search(r"Table '([^']+)'", raw_hand)
        table_name = table_match.group(1) if table_match else None
        
        if stages is None:
            stages = self._extract_stages(raw_hand, players)
        
        if summary_info is None:
            summary_info = self._extract_summary(raw_hand)
        
        if dealer_position is None:
            dealer_position = self._extract_dealer_position(raw_hand)
        
        # Create the basic pokergpt format
        pokergpt_format = {
            "basic_info": {
                "blinds": f"{blinds[0]}/{blinds[1]}",
                "players": [{"name": name, "stack": data["stack"]} for name, data in players.items()],
                "dealer_position": dealer_position,
                "dealer_player": dealer_player,
                "table_name": table_name,
                "small_blind_player": small_blind_player,
                "big_blind_player": big_blind_player
            },
            "stages": stages,
            "outcomes": {
                "winner": winner,
                "bb_won": bb_won
            }
        }
        
        # Add summary information
        if summary_info:
            pokergpt_format["summary"] = summary_info
        
        return pokergpt_format
    
    def _extract_dealer_position(self, raw_hand):
        # Extract dealer position
        dealer_match = re.search(r'Seat #(\d+) is the button', raw_hand)
        if dealer_match:
            return int(dealer_match.group(1))
        return None
    
    def _extract_stages(self, raw_hand, players, hand_id=None):
        # Extract information for each stage (preflop, flop, turn, river, showdown)
        stages = {}
        
        # Define stage markers in the hand history
        stage_markers = [
            ("preflop", "*** HOLE CARDS ***", "*** FLOP ***"),
            ("flop", "*** FLOP ***", "*** TURN ***"),
            ("turn", "*** TURN ***", "*** RIVER ***"),
            ("river", "*** RIVER ***", "*** SHOW DOWN ***"),
            ("showdown", "*** SHOW DOWN ***", "*** SUMMARY ***")  # Added showdown stage
        ]
        
        # Fallback end marker for all stages
        fallback_end_marker = "*** SUMMARY ***"
        
        for stage_name, start_marker, end_marker in stage_markers:
            if start_marker in raw_hand:
                start_idx = raw_hand.index(start_marker) + len(start_marker)
                
                # Find the end of this section
                if end_marker in raw_hand[start_idx:]:
                    end_idx = raw_hand.index(end_marker, start_idx)
                elif fallback_end_marker in raw_hand[start_idx:]:
                    # If standard end marker not found but SUMMARY exists, use that
                    end_idx = raw_hand.index(fallback_end_marker, start_idx)
                else:
                    # If no markers found, go to the end of the hand
                    end_idx = len(raw_hand)
                    
                stage_text = raw_hand[start_idx:end_idx].strip()
                
                # Process based on stage type
                if stage_name == "showdown":
                    # For showdown, extract player cards and hand descriptions
                    stages[stage_name] = self._parse_showdown(stage_text)
                else:
                    # For other stages, use existing action parsing
                    actions = self._parse_actions(stage_text, players, hand_id, stage_name)
                    
                    # For flop/turn/river, also extract community cards
                    cards = None
                    if stage_name != "preflop":
                        cards = self._extract_community_cards(stage_text, stage_name)
                    
                    stages[stage_name] = {
                        "actions": actions,
                        "community_cards": cards
                    }
        
        return stages
    
    def _parse_showdown(self, showdown_text: str) -> Dict[str, Any]:
        """Parse the showdown section to extract player cards and hand descriptions."""
        showdown_data = {
            "players": []
        }
        
        # Process each line in the showdown text
        for line in showdown_text.split('\n'):
            line = line.strip()
            if not line or ': ' not in line:
                continue
            
            # Handle lines like "PlayerName: shows [Ks Qd] (two pair, Queens and Tens)"
            show_match = re.search(r'(.*?): shows \[(.*?)\](?: \((.*?)\))?', line)
            if show_match:
                player_name = show_match.group(1).strip()
                cards_str = show_match.group(2).strip()
                hand_desc = show_match.group(3).strip() if show_match.group(3) else None
                
                # Split cards into a list
                cards = [card.strip() for card in cards_str.split() if card.strip()]
                
                # Add to showdown data
                showdown_data["players"].append({
                    "player": player_name,
                    "cards": cards,
                    "hand_description": hand_desc
                })
                
            # Handle lines like "PlayerName collected $48.54 from pot"
            collect_match = re.search(r'(.*?) collected \$?([\d.]+)', line)
            if collect_match:
                player_name = collect_match.group(1).strip()
                amount = float(collect_match.group(2))
                
                # Add collection info to showdown data
                if "collections" not in showdown_data:
                    showdown_data["collections"] = []
                    
                showdown_data["collections"].append({
                    "player": player_name,
                    "amount": amount
                })
        
        return showdown_data
    
    def _extract_summary(self, raw_hand: str) -> Dict[str, Any]:
        """Extract information from the summary section."""
        summary_data = {}
        
        # Check if summary section exists
        if "*** SUMMARY ***" not in raw_hand:
            return summary_data
            
        # Extract summary section
        summary_start = raw_hand.index("*** SUMMARY ***") + len("*** SUMMARY ***")
        summary_text = raw_hand[summary_start:].strip()
        
        # Extract pot and rake
        pot_match = re.search(r'Total pot \$?([\d.]+) \| Rake \$?([\d.]+)', summary_text)
        if pot_match:
            summary_data["pot_total"] = float(pot_match.group(1))
            summary_data["rake"] = float(pot_match.group(2))
        
        # Extract board
        board_match = re.search(r'Board \[(.*?)\]', summary_text)
        if board_match:
            board_str = board_match.group(1).strip()
            summary_data["board"] = [card.strip() for card in board_str.split() if card.strip()]
        
        # Extract player results
        player_results = []
        
        # Look for lines with seat information
        seat_pattern = r'Seat (\d+): (.*?) \((.*?)\) (.*)'
        for seat_match in re.finditer(seat_pattern, summary_text):
            seat_num = int(seat_match.group(1))
            player_name = seat_match.group(2).strip()
            position = seat_match.group(3).strip()
            result = seat_match.group(4).strip()
            
            player_result = {
                "seat": seat_num,
                "player": player_name,
                "position": position,
                "result": result
            }
            
            # Extract hand description if available
            hand_desc_match = re.search(r'showed \[.*?\] and (?:won|lost)(?: \$?[\d.]+)? with (.*)', result)
            if hand_desc_match:
                player_result["hand_description"] = hand_desc_match.group(1).strip()
                
            player_results.append(player_result)
        
        summary_data["player_results"] = player_results
        
        return summary_data
    
    def _parse_actions(self, stage_text, players=None, hand_id=None, stage_name=None):
        """
        Parse player actions from stage text with correct handling of full player names
        
        The key fix here is to properly split each line at the first colon to get the full player name,
        rather than using regex patterns that might truncate names with spaces.
        """
        actions = []
        
        # Process each line in the stage text
        for line in stage_text.split('\n'):
            line = line.strip()
            if not line or ': ' not in line:
                continue
            
            # Split at the first colon to get the full player name
            parts = line.split(': ', 1)
            if len(parts) != 2:
                continue
                
            player_name = parts[0].strip()
            action_text = parts[1].strip()
            
            # Log if player not in player list
            if self.debug_mode and players and player_name not in players:
                self.debug_log.append(f"ACTION PARSE: Player '{player_name}' in {stage_name} action not in player list (Hand {hand_id})")
                self.debug_log.append(f"  - Action line: '{line}'")
                self.debug_log.append(f"  - Known players: {list(players.keys())}")
                
                # Check if this player name is part of another player name
                for known_player in players.keys():
                    if player_name in known_player and player_name != known_player:
                        self.debug_log.append(f"  - *** PARTIAL NAME: '{player_name}' might be part of '{known_player}'")
            
            # Parse the action
            action_data = {"player": player_name}
            
            if action_text.startswith('raises '):
                action_data["action"] = "raises"
                # Try to extract amount and total
                amount_match = re.search(r'raises \$?([\d.]+)(?: to \$?([\d.]+))?', action_text)
                if amount_match:
                    try:
                        action_data["amount"] = float(amount_match.group(1))
                        if amount_match.group(2):
                            action_data["total"] = float(amount_match.group(2))
                    except (ValueError, IndexError):
                        pass
            elif action_text.startswith('calls '):
                action_data["action"] = "calls"
                amount_match = re.search(r'calls \$?([\d.]+)', action_text)
                if amount_match:
                    try:
                        action_data["amount"] = float(amount_match.group(1))
                    except ValueError:
                        pass
            elif action_text.startswith('bets '):
                action_data["action"] = "bets"
                amount_match = re.search(r'bets \$?([\d.]+)', action_text)
                if amount_match:
                    try:
                        action_data["amount"] = float(amount_match.group(1))
                    except ValueError:
                        pass
            elif action_text == 'folds':
                action_data["action"] = "folds"
            elif action_text.startswith('folds ['):
                # Handle "folds [cards]" actions
                action_data["action"] = "folds_show"
                # Extract cards shown
                cards_match = re.search(r'folds \[(.*?)\]', action_text)
                if cards_match:
                    cards_str = cards_match.group(1).strip()
                    action_data["cards"] = [card.strip() for card in cards_str.split() if card.strip()]
            elif action_text == 'checks':
                action_data["action"] = "checks"
            elif action_text == "doesn't show hand":
                action_data["action"] = "doesnt_show"
            elif action_text.startswith('shows '):
                action_data["action"] = "shows"
                # Try to extract cards and hand description
                show_match = re.search(r'shows \[(.*?)\](?: \((.*?)\))?', action_text)
                if show_match:
                    cards_str = show_match.group(1).strip()
                    hand_desc = show_match.group(2).strip() if show_match.group(2) else None
                    
                    # Split cards into a list
                    action_data["cards"] = [card.strip() for card in cards_str.split() if card.strip()]
                    if hand_desc:
                        action_data["hand_description"] = hand_desc
            else:
                # Unknown action, log and skip
                if self.debug_mode:
                    self.debug_log.append(f"Unknown action in line: '{line}'")
                continue
            
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
                            has_river, has_showdown, player_ids, played_at, table_name,
                            dealer_position, dealer_player, small_blind_player, big_blind_player,
                            pot_total, rake, board
                        ) VALUES (
                            %(hand_id)s, %(raw_text)s, %(pokergpt_format)s, %(game_type)s, %(blinds)s, %(big_blind)s,
                            %(player_count)s, %(winner)s, %(bb_won)s, %(has_preflop)s, %(has_flop)s, %(has_turn)s,
                            %(has_river)s, %(has_showdown)s, %(player_ids)s, %(played_at)s, %(table_name)s,
                            %(dealer_position)s, %(dealer_player)s, %(small_blind_player)s, %(big_blind_player)s,
                            %(pot_total)s, %(rake)s, %(board)s
                        )
                    """, {
                        **parsed_hand,
                        'pokergpt_format': json.dumps(parsed_hand['pokergpt_format']),
                        'blinds': parsed_hand['blinds']
                    })
            # Transaction is automatically committed if successful
            return True
        except Exception as e:
            # Transaction is already rolled back by the context manager
            if self.debug_mode:
                self.debug_log.append(f"Error inserting hand {parsed_hand.get('hand_id', 'unknown')}: {e}")
            else:
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
            if self.debug_mode:
                self.debug_log.append(f"Decode error at position {e.start} in file {file_path}")
            else:
                print(f"Decode error at position {e.start} in file {file_path}")
            
            # Read the file in binary mode
            with open(file_path, 'rb') as f:
                raw_data = f.read()
            
            # Implement a hybrid approach - read as UTF-8 but replace problematic characters
            content = raw_data.decode('utf-8', errors='replace')
            if self.debug_mode:
                self.debug_log.append(f"Continuing with replaced characters in file {file_path}")
            else:
                print(f"Continuing with replaced characters in file {file_path}")
            
            # Optionally log files with encoding issues for review
            with open('encoding_issues.log', 'a') as log:
                log.write(f"{file_path}: {str(e)}\n")
        
        # Process hand histories with improved splitting
        hand_splits = re.split(r'(?=PokerStars Hand #)', content)
        
        hands_processed = 0
        hands_failed = 0
        hands_with_missing_players = 0
        
        for i, hand_text in enumerate(hand_splits):
            if not hand_text.strip():
                continue
                
            # Skip entries that don't start with "PokerStars Hand #" (typically the first split)
            if not hand_text.lstrip().startswith("PokerStars Hand #"):
                if i == 0:  # Only log this for the first split to avoid confusion
                    if self.debug_mode:
                        self.debug_log.append(f"Skipping header or incomplete hand in {file_path}")
                    else:
                        print(f"Skipping header or incomplete hand in {file_path}")
                continue
                
            try:
                parsed_hand = self.parse_pokerstars_hand(hand_text)
                
                # Check if this hand had missing players
                hand_id = parsed_hand.get('hand_id', 'unknown')
                if self.debug_mode and os.path.exists(f"diagnostic_logs/hand_{hand_id}_missing_players.txt"):
                    hands_with_missing_players += 1
                
                success = self.insert_hand(parsed_hand)
                if success:
                    hands_processed += 1
                else:
                    hands_failed += 1
                    
                if hands_processed % 100 == 0:
                    if self.debug_mode:
                        self.debug_log.append(f"Processed {hands_processed} hands from {file_path}")
                    else:
                        print(f"Processed {hands_processed} hands from {file_path}")
            except Exception as e:
                hands_failed += 1
                if self.debug_mode:
                    self.debug_log.append(f"Error processing hand: {e}")
                else:
                    print(f"Error processing hand: {e}")
                continue
        
        summary = f"File {file_path} complete: {hands_processed} hands processed, {hands_failed} failed"
        if self.debug_mode:
            summary += f", {hands_with_missing_players} hands with missing players"
        
        if self.debug_mode:
            self.debug_log.append(summary)
        else:
            print(summary)
    
    def save_debug_log(self, filename='parser_debug.log'):
        """Save the debug log to a file"""
        if self.debug_mode and self.debug_log:
            with open(filename, 'w') as f:
                for line in self.debug_log:
                    f.write(f"{line}\n")
            print(f"Debug log saved to {filename}")
    
    def close(self):
        """Close the database connection"""
        self.conn.close()


def main():
    parser = argparse.ArgumentParser(description='Parse poker hand histories and store in database')
    parser.add_argument('--input-dir', required=True, help='Directory containing hand history files')
    parser.add_argument('--db-connection', required=True, help='Database connection string')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--debug-log', default='parser_debug.log', help='Debug log file name')
    
    args = parser.parse_args()
    
    import os
    processor = PokerHandProcessor(args.db_connection, debug_mode=args.debug)
    
    # Process each file in the input directory
    for filename in os.listdir(args.input_dir):
        if filename.endswith('.txt'):
            file_path = os.path.join(args.input_dir, filename)
            print(f"Processing file: {file_path}")
            processor.process_hand_file(file_path)
    
    # Save debug log if in debug mode
    if args.debug:
        processor.save_debug_log(args.debug_log)
    
    processor.close()
    print("Processing complete")


if __name__ == "__main__":
    main()