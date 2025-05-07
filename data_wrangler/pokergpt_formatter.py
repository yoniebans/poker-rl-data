import re
from typing import Dict, List, Any, Optional, Tuple
from data_wrangler.poker_hand_evaluator import PokerHandEvaluator


class PokerGPTFormatter:
    """
    Transform structured poker hand data into the PokerGPT prompt format 
    as described in the research paper.
    """
    
    def __init__(self):
        # Card characteristics lookup
        self.suit_patterns = {
            'h': 'hearts',
            'd': 'diamonds',
            'c': 'clubs',
            's': 'spades'
        }
        
        # Card value map for numeric comparison
        self.value_map = {
            'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14
        }
        
    def _get_card_characteristics(self, cards: List[str]) -> List[str]:
        """
        Determine card characteristics for PokerGPT format (suit, high, close)
        
        Args:
            cards: List of card codes (e.g. ["Th", "Ah"])
            
        Returns:
            List of characteristics strings (e.g. ["suit", "high", "close"])
        """
        if not cards or len(cards) != 2:
            return []
        
        characteristics = []
        
        # Extract card values and suits
        card1_value = cards[0][0]
        card1_suit = cards[0][1]
        card2_value = cards[1][0]
        card2_suit = cards[1][1]
        
        # Convert card values to numeric
        val1 = int(self.value_map.get(card1_value, card1_value))
        val2 = int(self.value_map.get(card2_value, card2_value))
        
        # Check for same suit
        if card1_suit == card2_suit:
            characteristics.append("suit")
        
        # Check for high cards (9 or higher)
        if val1 > 9 or val2 > 9:
            characteristics.append("high")
        
        # Check for close values (difference less than 5)
        if abs(val1 - val2) < 5:
            characteristics.append("close")
        
        return characteristics
    
    def _determine_hand_rank(self, private_cards: List[str], community_cards: List[str]) -> str:
        """
        Determine the hand rank based on available cards.
        Uses the PokerHandEvaluator for accurate ranking.
        
        Args:
            private_cards: Player's private cards
            community_cards: Visible community cards
            
        Returns:
            String representation of hand rank (e.g. "High", "Pair", "Flush")
        """
        # Use the poker hand evaluator to get an accurate rank
        eval_result = PokerHandEvaluator.evaluate_hand(private_cards, community_cards)
        return eval_result.get('rank', 'Unknown')
    
    def _extract_private_cards(self, hand_data: Dict[str, Any], player_name: str) -> List[str]:
        """
        Extract private cards for a player from the hand data.
        
        This method searches through the poker hand data to find the private cards
        for the specified player, particularly from showdown information.
        
        Args:
            hand_data: The structured hand data
            player_name: Name of the player
            
        Returns:
            List of card codes or placeholders if not found
        """
        pokergpt_format = hand_data.get('pokergpt_format', {})
        if isinstance(pokergpt_format, str):
            import json
            pokergpt_format = json.loads(pokergpt_format)

        # First try to find cards in the raw_text if available
        raw_text = hand_data.get('raw_text', '')
        if raw_text and player_name:
            # Check for showdown pattern: "player_name: shows [card1 card2]"
            pattern = rf'{re.escape(player_name)}: shows \[(.*?)\]'
            match = re.search(pattern, raw_text)
            if match:
                cards_str = match.group(1)
                # Cards might be formatted as "Tc 4c" or "T♣ 4♣" or other variations
                cards = re.findall(r'([2-9TJQKA][cdhs♣♦♥♠])', cards_str)
                if len(cards) == 2:
                    # Convert suit symbols to letters if needed
                    cards = [
                        card.replace('♣', 'c').replace('♦', 'd')
                           .replace('♥', 'h').replace('♠', 's')
                        for card in cards
                    ]
                    return cards

        # Try to find in summary section
        if 'summary' in pokergpt_format:
            summary = pokergpt_format.get('summary', {})
            for player_summary in summary.get('players', []):
                if player_summary.get('name') == player_name and 'cards' in player_summary:
                    return player_summary.get('cards', [])

        # Try to find in player-specific data
        if 'players' in pokergpt_format:
            for player in pokergpt_format.get('players', []):
                if player.get('name') == player_name and 'cards' in player:
                    return player.get('cards', [])

        # Try to find in showdown data
        if 'showdown' in pokergpt_format:
            showdown = pokergpt_format.get('showdown', {})
            for showdown_player in showdown.get('players', []):
                if showdown_player.get('name') == player_name and 'cards' in showdown_player:
                    return showdown_player.get('cards', [])

        # Final attempt: search directly in the raw JSON structure (different formats)
        def search_cards(obj, target_player):
            """Recursively search for player cards in nested structure"""
            if isinstance(obj, dict):
                if obj.get('player') == target_player and 'cards' in obj:
                    return obj['cards']
                
                for key, value in obj.items():
                    if key == 'players' and isinstance(value, list):
                        for player in value:
                            if player.get('name') == target_player and 'cards' in player:
                                return player['cards']
                    
                    result = search_cards(value, target_player)
                    if result:
                        return result
            
            elif isinstance(obj, list):
                for item in obj:
                    result = search_cards(item, target_player)
                    if result:
                        return result
            
            return None

        cards = search_cards(pokergpt_format, player_name)
        if cards:
            return cards

        # If we still haven't found cards, return placeholder cards
        # This should rarely happen for showdown hands, but just in case
        return ['Th', 'Ah']  # Default to high suited cards
    
    def format_hand_to_pokergpt_prompt(self, 
                                    hand_data: Dict[str, Any], 
                                    player_perspective: str = None,
                                    stage: str = None) -> str:
        """
        Format a poker hand into the PokerGPT prompt format.
        
        Args:
            hand_data: The structured hand data
            player_perspective: Which player's perspective to format from (default: winner)
            stage: Which game stage to format for (default: last stage in the hand)
            
        Returns:
            String formatted according to PokerGPT prompt structure
        """
        pokergpt_format = hand_data.get('pokergpt_format', {})
        if isinstance(pokergpt_format, str):
            import json
            pokergpt_format = json.loads(pokergpt_format)
            
        # Basic info
        basic_info = pokergpt_format.get('basic_info', {})
        players = basic_info.get('players', [])
        blinds = basic_info.get('blinds', '$0.50/$1.00')
        dealer_position = basic_info.get('dealer_position', 1)
        
        # If no specific player is provided, use the winner
        if not player_perspective:
            player_perspective = hand_data.get('winner')
        
        # Find the player's seat
        player_seat = None
        for i, player in enumerate(players):
            if player.get('name') == player_perspective:
                player_seat = i + 1  # 1-indexed seats
                break
                
        if not player_seat:
            return "Error: Could not find player perspective in hand data"
            
        # Determine player order based on dealer position
        total_players = len(players)
        player_order = []
        seat_order = list(range(1, total_players + 1))
        # Reorder seats so dealer is first
        dealer_idx = dealer_position - 1
        player_order = seat_order[dealer_idx:] + seat_order[:dealer_idx]
        
        # Get stages and determine which stage to represent
        stages = pokergpt_format.get('stages', {})
        available_stages = list(stages.keys())
        
        if not stage and available_stages:
            # Default to the last stage in the hand
            stage = available_stages[-1]
        elif stage not in available_stages:
            # If requested stage not available, use the last one
            stage = available_stages[-1] if available_stages else None
            
        if not stage:
            return "Error: No game stages found in hand data"
            
        # Get community cards for the stage
        community_cards = ['**', '**', '**', '**', '**']  # Default to hidden
        
        # Fill in community cards based on stage
        if stage == 'flop' and 'flop' in stages:
            flop_cards = stages['flop'].get('community_cards', [])
            if isinstance(flop_cards, list) and len(flop_cards) == 3:
                community_cards[:3] = flop_cards
        elif stage == 'turn' and 'turn' in stages:
            if 'flop' in stages:
                flop_cards = stages['flop'].get('community_cards', [])
                if isinstance(flop_cards, list) and len(flop_cards) == 3:
                    community_cards[:3] = flop_cards
            turn_card = stages['turn'].get('community_cards')
            if turn_card:
                community_cards[3] = turn_card
        elif stage == 'river' and 'river' in stages:
            if 'flop' in stages:
                flop_cards = stages['flop'].get('community_cards', [])
                if isinstance(flop_cards, list) and len(flop_cards) == 3:
                    community_cards[:3] = flop_cards
            if 'turn' in stages:
                turn_card = stages['turn'].get('community_cards')
                if turn_card:
                    community_cards[3] = turn_card
            river_card = stages['river'].get('community_cards')
            if river_card:
                community_cards[4] = river_card
        elif stage == 'showdown' and 'showdown' in stages:
            # For showdown, we want to show all community cards from previous stages
            if 'flop' in stages:
                flop_cards = stages['flop'].get('community_cards', [])
                if isinstance(flop_cards, list) and len(flop_cards) == 3:
                    community_cards[:3] = flop_cards
            if 'turn' in stages:
                turn_card = stages['turn'].get('community_cards')
                if turn_card:
                    community_cards[3] = turn_card
            if 'river' in stages:
                river_card = stages['river'].get('community_cards')
                if river_card:
                    community_cards[4] = river_card
                
        # Get player's private cards
        private_cards = self._extract_private_cards(hand_data, player_perspective)

        # Get card characteristics
        card_characteristics = self._get_card_characteristics(private_cards)
        
        # Determine hand rank
        hand_rank = self._determine_hand_rank(private_cards, community_cards)

        # Track player actions and states
        player_actions = {}
        
        # Initialize player stacks with default value for missing players
        default_stack = 100.0
        player_stacks = {}
        player_names = set()
        
        # First, initialize stacks for known players
        for p in players:
            p_name = p.get('name')
            if p_name:
                player_stacks[p_name] = float(p.get('stack', default_stack))
                player_names.add(p_name)
        
        discard_status = {p_name: False for p_name in player_names}
        
        # Process actions for each stage up to the current one
        stage_order = ['preflop', 'flop', 'turn', 'river', 'showdown']  # Added showdown here
        
        # Get stage index, with fallback for showdown or unknown stages
        try:
            stage_idx = stage_order.index(stage)
        except ValueError:
            # If stage not in stage_order, just use all stages
            stage_idx = len(stage_order) - 1
        
        # Track all players mentioned in actions
        all_players_in_actions = set()
        
        # First pass - collect all player names from actions
        for s in stage_order[:stage_idx+1]:
            if s in stages:
                stage_actions = stages[s].get('actions', [])
                for action in stage_actions:
                    p_name = action.get('player')
                    if p_name:
                        all_players_in_actions.add(p_name)
        
        # Initialize stacks for any players found in actions but not in the player list
        for p_name in all_players_in_actions:
            if p_name not in player_stacks:
                player_stacks[p_name] = default_stack
                discard_status[p_name] = False
                player_names.add(p_name)
        
        # Second pass - process actions
        for s in stage_order[:stage_idx+1]:
            if s in stages:
                stage_actions = stages[s].get('actions', [])
                for action in stage_actions:
                    p_name = action.get('player')
                    p_action = action.get('action')
                    
                    if not p_name or not p_action:
                        continue
                    
                    # Track actions for each player
                    if p_name not in player_actions:
                        player_actions[p_name] = []
                    
                    action_str = p_action
                    if 'amount' in action:
                        action_str += f" {action['amount']}"
                    if 'total' in action:
                        action_str += f" to {action['total']}"
                        
                    player_actions[p_name].append(action_str)
                    
                    # Update discard status - players who fold are discarded
                    if p_action == 'folds':
                        discard_status[p_name] = True
                        
                    # Update player stacks based on actions
                    if p_action in ['calls', 'bets', 'raises'] and 'amount' in action:
                        try:
                            player_stacks[p_name] -= float(action['amount'])
                            # Ensure stack doesn't go negative
                            if player_stacks[p_name] < 0:
                                player_stacks[p_name] = 0
                        except (ValueError, KeyError) as e:
                            # Handle conversion errors or missing players gracefully
                            pass
        
        # Calculate pot value - simplified approximation
        pot_value = 0
        for p_name in player_names:
            if p_name in player_actions:  # Only count players who have taken action
                initial_stack = default_stack
                for p in players:
                    if p.get('name') == p_name:
                        initial_stack = float(p.get('stack', default_stack))
                        break
                
                current_stack = player_stacks.get(p_name, initial_stack)
                pot_value += max(0, initial_stack - current_stack)  # Ensure no negative contributions
        
        # Format the prompt following PokerGPT paper structure
        prompt = f"""You are an experienced gambler. Now you need to assist me to make decisions in Texas Hold'em games. You have been provided with a series of observable information:

    Player amount: [{total_players}], Currency: USD, Blind value: [{blinds}], Order: {str(player_order)}, Seat {dealer_position} is the button.

    My cards: {private_cards}, the characteristics of my cards: {card_characteristics}, My seat: [Seat {player_seat}]

    Stage: "{stage.upper()}", Public cards: {community_cards}
    My rank: ["{hand_rank}"], Money: [{player_stacks.get(player_perspective, default_stack):.2f}], Action: {player_actions.get(player_perspective, [])}
    """
        
        # Add other players' information
        for p in players:
            p_name = p.get('name')
            if p_name and p_name != player_perspective:
                p_cards = ['**', '**']  # Hidden cards for opponents
                p_seat = p.get('seat', players.index(p) + 1)
                prompt += f"Seat {p_seat}: {p_cards}, Money: [{player_stacks.get(p_name, default_stack):.2f}], Action: {player_actions.get(p_name, [])}, Discard: [{discard_status.get(p_name, False)}]\n"
        
        # Also add any players mentioned in actions but not in the player list
        for p_name in all_players_in_actions:
            if p_name not in [p.get('name') for p in players] and p_name != player_perspective:
                prompt += f"{p_name}: ['**', '**'], Money: [{player_stacks.get(p_name, default_stack):.2f}], Action: {player_actions.get(p_name, [])}, Discard: [{discard_status.get(p_name, False)}]\n"
        
        # Add pot value and available actions
        prompt += f"\nThe pot value is [{pot_value:.2f}]\n"
        
        # Determine available actions based on game state
        available_actions = ["fold", "check", "call", "bet", "raise"]
        
        # Adjust available actions based on game context
        if any(a.get('action') == 'bets' for a in stages.get(stage, {}).get('actions', [])):
            # If someone has bet, can't check
            if "check" in available_actions:
                available_actions.remove("check")
        else:
            # If nobody has bet, can't call or raise
            if "call" in available_actions:
                available_actions.remove("call")
            if "raise" in available_actions:
                available_actions.remove("raise")
                
        # Generate formatted action prompt
        action_prompt = f"The actions can be: {available_actions}. What should I do?"
        
        # Add bet sizing options for bet/raise actions
        if "bet" in available_actions or "raise" in available_actions:
            player_stack = player_stacks.get(player_perspective, default_stack)
            bet_options = [0, 0.05, 0.15, 0.3, 0.5, 1, 2.5]
            # Add all-in option
            bet_options.append(player_stack)
            # Filter out bet sizes larger than player's stack
            valid_options = [opt for opt in bet_options if opt <= player_stack]
            action_prompt += f" If I choose to \"bet\" or \"raise\", then how much? Choose a number from {valid_options}."
        
        prompt += action_prompt
        
        return prompt
    
    def format_batch_for_training(self, 
                                 hands_data: List[Dict[str, Any]], 
                                 include_actions: bool = True) -> List[Dict[str, Any]]:
        """
        Format a batch of hands for training a PokerGPT model.
        
        Args:
            hands_data: List of structured hand data dictionaries
            include_actions: Whether to include the winning action as the target
            
        Returns:
            List of dictionaries with 'prompt' and optionally 'action' keys
        """
        formatted_data = []
        
        for hand in hands_data:
            # Get the prompt
            prompt = self.format_hand_to_pokergpt_prompt(hand)
            
            result = {'prompt': prompt}
            
            # Optionally extract the winning action
            if include_actions:
                winner = hand.get('winner')
                if winner:
                    # Find the winning action in the hand data
                    pokergpt_format = hand.get('pokergpt_format', {})
                    if isinstance(pokergpt_format, str):
                        import json
                        pokergpt_format = json.loads(pokergpt_format)
                    
                    stages = pokergpt_format.get('stages', {})
                    
                    # Get the last stage with actions
                    stage_order = ['river', 'turn', 'flop', 'preflop']
                    winner_action = None
                    
                    for stage in stage_order:
                        if stage in stages:
                            stage_actions = stages[stage].get('actions', [])
                            # Find the last action by the winner
                            for action in reversed(stage_actions):
                                if action.get('player') == winner:
                                    action_str = action.get('action', '')
                                    if 'amount' in action:
                                        action_str += f" {action['amount']}"
                                    winner_action = action_str
                                    break
                            
                            if winner_action:
                                break
                    
                    if winner_action:
                        result['action'] = winner_action
            
            formatted_data.append(result)
            
        return formatted_data