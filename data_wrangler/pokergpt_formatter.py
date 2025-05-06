# data_wrangler/pokergpt_formatter.py
import re
from typing import Dict, List, Any, Optional, Tuple

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
            's': 'spad
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
        
        Args:
            private_cards: Player's private cards
            community_cards: Visible community cards
            
        Returns:
            String representation of hand rank (e.g. "High", "Pair", "Flush")
        
        Note:
            This is a simplified implementation. A production system should
            use a proper poker hand evaluator library.
        """
        # Check if we're in preflop or have no community cards
        if not community_cards or all(card == '**' for card in community_cards):
            # Preflop - basic ranking
            values = [card[0] for card in private_cards]
            suits = [card[1] for card in private_cards]
            
            # Check for pairs
            if values[0] == values[1]:
                return "Pair"
            
            # Check for high cards
            high_values = {'A', 'K', 'Q', 'J', 'T'}
            if any(v in high_values for v in values):
                return "High"
            
            return "Low"
            
        # For post-flop, we would normally evaluate the actual hand
        # This is a simplified placeholder implementation
        visible_cards = [c for c in community_cards if c != '**']
        
        # Check for flush potential
        suits = [card[1] for card in private_cards] + [c[1] for c in visible_cards if len(c) > 1]
        suit_counts = {}
        for suit in suits:
            suit_counts[suit] = suit_counts.get(suit, 0) + 1
            if suit_counts[suit] >= 5:
                return "Flush"
                
        # Check for pairs
        all_values = [card[0] for card in private_cards] + [c[0] for c in visible_cards if len(c) > 1]
        value_counts = {}
        for val in all_values:
            value_counts[val] = value_counts.get(val, 0) + 1
        
        # Count pairs, three of a kind, etc.
        pairs = sum(1 for v, count in value_counts.items() if count == 2)
        three_kind = any(count == 3 for v, count in value_counts.items())
        four_kind = any(count == 4 for v, count in value_counts.items())
        
        if four_kind:
            return "Four of a Kind"
        elif three_kind and pairs > 0:
            return "Full House"
        elif three_kind:
            return "Three of a Kind"
        elif pairs >= 2:
            return "Two Pair"
        elif pairs == 1:
            return "Pair"
            
        # Default to high card
        return "High"
    
    def _extract_private_cards(self, hand_data: Dict[str, Any], player_name: str) -> List[str]:
        """
        Extract private cards for a player if available.
        
        In many hand histories, private cards might only be available for players 
        who went to showdown, or might not be available at all.
        
        Args:
            hand_data: The structured hand data
            player_name: Name of the player
            
        Returns:
            List of card codes or placeholders
        """
        # This is a simplified implementation
        # In a real system, you would extract the actual private cards if recorded
        
        # For now, return placeholder cards
        # High Ace-Ten suited as a reasonable placeholder
        return ['Th', 'Ah']
    
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
                
        # Get player's private cards
        private_cards = self._extract_private_cards(hand_data, player_perspective)

        # Get card characteristics
        card_characteristics = self._get_card_characteristics(private_cards)
        
        # Determine hand rank
        hand_rank = self._determine_hand_rank(private_cards, community_cards)

        # Track player actions and states
        player_actions = {}
        player_stacks = {p.get('name'): p.get('stack', 100) for p in players}
        discard_status = {p.get('name'): False for p in players}
        
        # Process actions for each stage up to the current one
        stage_order = ['preflop', 'flop', 'turn', 'river']
        stage_idx = stage_order.index(stage)
        
        for s in stage_order[:stage_idx+1]:
            if s in stages:
                stage_actions = stages[s].get('actions', [])
                for action in stage_actions:
                    p_name = action.get('player')
                    p_action = action.get('action')
                    
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
                        player_stacks[p_name] -= float(action['amount'])
        
        # Calculate pot value - simplified approximation
        starting_stacks = {p.get('name'): p.get('stack', 100) for p in players}
        pot_value = sum([
            starting_stacks.get(p_name, 100) - player_stacks.get(p_name, 100)
            for p_name in player_stacks
        ])
        
        # Format the prompt following PokerGPT paper structure
        prompt = f"""You are an experienced gambler. Now you need to assist me to make decisions in Texas Hold'em games. You have been provided with a series of observable information:

Player amount: [{total_players}], Currency: USD, Blind value: [{blinds}], Order: {str(player_order)}, Seat {dealer_position} is the button.

My cards: {private_cards}, the characteristics of my cards: {card_characteristics}, My seat: [Seat {player_seat}]

Stage: "{stage.upper()}", Public cards: {community_cards}
My rank: ["{hand_rank}"], Money: [{player_stacks.get(player_perspective, 100):.2f}], Action: {player_actions.get(player_perspective, [])}
"""
        
        # Add other players' information
        for p in players:
            p_name = p.get('name')
            if p_name != player_perspective:
                p_cards = ['**', '**']  # Hidden cards for opponents
                p_seat = p.get('seat', players.index(p) + 1)
                prompt += f"Seat {p_seat}: {p_cards}, Money: [{player_stacks.get(p_name, 100):.2f}], Action: {player_actions.get(p_name, [])}, Discard: [{discard_status.get(p_name, False)}]\n"
                
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
            player_stack = player_stacks.get(player_perspective, 100)
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