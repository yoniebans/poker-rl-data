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
        
    def _analyze_betting_context(self, stage_actions: List[Dict[str, Any]]) -> Dict[str, bool]:
        """
        Analyze the betting context of the current stage.
        
        Args:
            stage_actions: List of actions in the current betting stage
            
        Returns:
            Dictionary with betting context information:
            - has_bet: Whether anyone has bet in this round
            - has_raise: Whether anyone has raised in this round
            - facing_all_in: Whether player is facing an all-in
        """
        context = {
            'has_bet': False,
            'has_raise': False,
            'facing_all_in': False
        }
        
        for action in stage_actions:
            action_type = action.get('action', '')
            
            # Check for bets
            if action_type in ['bets', 'raises']:
                if not context['has_bet']:
                    context['has_bet'] = True
                else:
                    # If there's already a bet and someone raises, mark as raise
                    context['has_raise'] = True
                    
            # Check for all-ins - either as text in action_type or as a dedicated flag
            if 'all-in' in action_type.lower() or action.get('is_all_in', False):
                context['facing_all_in'] = True
        
        return context
        
    def _is_heads_up(self, stage_actions: List[Dict[str, Any]]) -> bool:
        """
        Determine if the current hand is heads-up (only two active players).
        
        Args:
            stage_actions: List of actions in the current betting stage
            
        Returns:
            True if only two players are active in the hand, False otherwise
        """
        active_players = set()
        folded_players = set()
        
        for action in stage_actions:
            player = action.get('player')
            action_type = action.get('action', '')
            
            if player and action_type:
                # Add player to active list if they're taking an action
                active_players.add(player)
                
                # If a player folds, add them to folded players
                if action_type == 'folds':
                    folded_players.add(player)
        
        # Calculate number of active players (total minus folded)
        active_count = len(active_players) - len(folded_players)
        
        # Return True if exactly two players remain active
        return active_count == 2
        
    def _determine_available_actions(self, stage_actions: List[Dict[str, Any]]) -> List[str]:
        """
        Determine available actions based on betting context.
        
        Args:
            stage_actions: List of actions in the current betting stage
            
        Returns:
            List of available action types following poker terminology
        """
        context = self._analyze_betting_context(stage_actions)
        
        # Handle special case: facing all-in with just two players
        if context['facing_all_in'] and self._is_heads_up(stage_actions):
            return ["fold", "call"]
        
        # Regular action determination following the rules
        if context['has_raise']:
            # Someone has already raised
            return ["fold", "call", "re-raise", "all-in"]
        elif context['has_bet']:
            # Someone has bet but no raises yet
            return ["fold", "call", "raise", "all-in"]
        else:
            # No one has bet yet
            return ["fold", "check", "bet", "all-in"]
            
    def _get_current_bet(self, stage_actions: List[Dict[str, Any]], hand_id: str = "unknown") -> float:
        """
        Get the current bet amount in the betting round.
        
        Args:
            stage_actions: List of actions in the current betting stage
            hand_id: The hand identifier for debugging purposes
            
        Returns:
            The current bet amount as a float
            
        Raises:
            ValueError: If a bet/raise is expected but not found or invalid
        """
        if not stage_actions:
            return 0.0
        
        # Find the last bet or raise action
        for action in reversed(stage_actions):
            action_type = action.get('action', '')
            
            if action_type in ['bets', 'raises']:
                # Check if the action has an amount or total attribute
                if 'total' in action:
                    try:
                        return float(action.get('total', 0.0))
                    except (ValueError, TypeError):
                        raise ValueError(f"Hand {hand_id}: Invalid 'total' value in bet/raise action")
                elif 'amount' in action:
                    try:
                        return float(action.get('amount', 0.0))
                    except (ValueError, TypeError):
                        raise ValueError(f"Hand {hand_id}: Invalid 'amount' value in bet/raise action")
                else:
                    raise ValueError(f"Hand {hand_id}: Found bet/raise action without amount or total")
        
        # If no bet/raise action found, return 0 (no current bet)
        return 0.0
        
    def _generate_bet_sizing_options(self, action_type: str, game_state: Dict[str, Any], hand_id: str = "unknown") -> List[float]:
        """
        Generate appropriate bet sizing options based on action type and game state.
        
        Args:
            action_type: The type of action (bet, raise, re-raise)
            game_state: Current game state with pot size, big blind, etc.
            hand_id: The hand identifier for debugging purposes
            
        Returns:
            List of formatted bet size options
            
        Raises:
            ValueError: If required game state information is missing or invalid
        """
        # Extract and validate required game state values
        try:
            big_blind = float(game_state.get('big_blind', 0))
            pot_size = float(game_state.get('pot_size', 0))
            player_stack = float(game_state.get('player_stack', 0))
            
            if big_blind <= 0:
                raise ValueError(f"Hand {hand_id}: Invalid big blind value: {big_blind}")
            if pot_size <= 0:
                raise ValueError(f"Hand {hand_id}: Invalid pot size value: {pot_size}")
            if player_stack <= 0:
                raise ValueError(f"Hand {hand_id}: Invalid player stack value: {player_stack}")
                
        except (TypeError, ValueError) as e:
            raise ValueError(f"Hand {hand_id}: Invalid game state values - {str(e)}")
        
        # Check if we have a winning action amount to include
        winning_amount = None
        if 'winning_amount' in game_state and game_state['winning_amount'] is not None:
            try:
                winning_amount = float(game_state['winning_amount'])
                # Validate it's a reasonable amount
                if winning_amount <= 0 or winning_amount >= player_stack:
                    print(f"Warning: Hand {hand_id}: Winning amount {winning_amount} is outside valid range - ignoring")
                    winning_amount = None
            except (ValueError, TypeError):
                print(f"Warning: Hand {hand_id}: Invalid winning amount {game_state['winning_amount']} - ignoring")
                winning_amount = None
        
        # For raise/re-raise actions, we need current_bet
        current_bet = 0.0
        if action_type in ["raise", "re-raise"]:
            if 'current_bet' not in game_state:
                raise ValueError(f"Hand {hand_id}: Missing current_bet for {action_type} action")
            try:
                current_bet = float(game_state['current_bet'])
                if current_bet <= 0:
                    raise ValueError(f"Hand {hand_id}: Invalid current bet value: {current_bet}")
            except (TypeError, ValueError) as e:
                raise ValueError(f"Hand {hand_id}: Invalid current_bet value - {str(e)}")
        
        # Generate sizing options based on action type
        options = []
        
        if action_type == "bet":
            # First to put money in this round
            
            # Mix of BB-based and pot-based options
            # Min bet is usually 1BB for no-limit games
            min_bet = big_blind
            
            # Generate standard sizing options for betting
            bb_options = [
                round(big_blind, 2),        # 1BB (min bet)
                round(big_blind * 2, 2),    # 2BB
                round(big_blind * 3, 2),    # 3BB
            ]
            
            pot_options = [
                round(pot_size * 0.5, 2),   # Half pot
                round(pot_size * 0.75, 2),  # 3/4 pot
                round(pot_size, 2),         # Full pot
                round(pot_size * 1.5, 2),   # 1.5x pot
            ]
            
            # Combine options based on context
            if pot_size < big_blind * 4:
                # Small pot, focus on BB-based options
                options = bb_options
            else:
                # Larger pot, include both types
                options = bb_options + pot_options
                
        elif action_type == "raise":
            # Raising someone else's bet
            # Min raise is typically the current bet amount + the size of the last bet
            min_raise = current_bet * 2  # Simplified - assumes original bet = current bet
            
            # Standard raise sizings
            options = [
                round(min_raise, 2),                             # Min raise
                round(current_bet + big_blind * 3, 2),          # Current bet + 3BB
                round(current_bet + pot_size * 0.5, 2),         # Current bet + half pot
                round(current_bet + pot_size * 0.75, 2),        # Current bet + 3/4 pot
                round(current_bet + pot_size, 2),               # Current bet + pot
            ]
            
        elif action_type == "re-raise":
            # Re-raising after someone has already raised
            min_reraise = current_bet * 2  # Simplified minimum re-raise
            
            # Standard re-raise sizings
            options = [
                round(min_reraise, 2),                          # Min re-raise
                round(current_bet * 2.5, 2),                    # 2.5x current bet
                round(current_bet * 3, 2),                      # 3x current bet
                round(pot_size * 1.5, 2),                      # 1.5x pot
                round(pot_size * 2, 2),                        # 2x pot
            ]
        
        # Add winning amount if available and applicable
        if winning_amount is not None:
            # Round to 2 decimal places for consistency
            winning_amount = round(winning_amount, 2)
            options.append(winning_amount)
        
        # Filter options:
        # 1. Must be less than player stack (can't bet more than you have)
        # 2. Must be unique values
        # 3. Must be at least minimum bet/raise amount
        valid_options = []
        min_required = big_blind if action_type == "bet" else current_bet * 2
        
        seen_values = set()
        for opt in options:
            # Skip invalid options
            if opt >= player_stack or opt < min_required:
                continue
                
            # Round to 2 decimal places for display
            rounded_opt = round(opt, 2)
            
            # Check for duplicates (after rounding)
            if rounded_opt in seen_values:
                continue
                
            valid_options.append(rounded_opt)
            seen_values.add(rounded_opt)
        
        # Add at least one option if all were filtered out but player can still bet
        if not valid_options and min_required < player_stack:
            valid_options.append(round(min_required, 2))
            
        # If we have a winning amount and it's not in our options (e.g., it was filtered out),
        # add it explicitly as long as it's not all-in
        if winning_amount is not None and winning_amount not in valid_options and winning_amount < player_stack:
            valid_options.append(winning_amount)
        
        # Sort in ascending order
        return sorted(valid_options)
    
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
        
        # Calculate pot value - use pot_total from hand_data if available
        pot_value = 0
        
        # First try to use the pot_total from hand_data if available
        if 'pot_total' in hand_data and hand_data['pot_total'] is not None:
            try:
                pot_value = float(hand_data['pot_total'])
            except (ValueError, TypeError):
                # If pot_total conversion fails, fall back to calculating from actions
                pot_value = 0
        
        # If no pot_total or conversion failed, calculate from player actions
        if pot_value <= 0:
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
        
        # Add other players' information - keep consistent indentation for all seats
        for p in players:
            p_name = p.get('name')
            if p_name and p_name != player_perspective:
                p_cards = ['**', '**']  # Hidden cards for opponents
                p_seat = p.get('seat', players.index(p) + 1)
                prompt += f"    Seat {p_seat}: {p_cards}, Money: [{player_stacks.get(p_name, default_stack):.2f}], Action: {player_actions.get(p_name, [])}, Discard: [{discard_status.get(p_name, False)}]\n"
        
        # Also add any players mentioned in actions but not in the player list
        for p_name in all_players_in_actions:
            if p_name not in [p.get('name') for p in players] and p_name != player_perspective:
                prompt += f"    {p_name}: ['**', '**'], Money: [{player_stacks.get(p_name, default_stack):.2f}], Action: {player_actions.get(p_name, [])}, Discard: [{discard_status.get(p_name, False)}]\n"
        
        # Add pot value and available actions - no indentation for these lines
        prompt += f"\nThe pot value is [{pot_value:.2f}]\n"
        
        # Get hand_id for error messages
        hand_id = hand_data.get('hand_id', 'unknown')
        
        # Determine available actions based on betting context - we don't catch errors here
        # because if we can't determine valid actions, we should fail and fix the issue
        stage_actions = stages.get(stage, {}).get('actions', [])
        available_actions = self._determine_available_actions(stage_actions)
        
        # Check if the player is facing an all-in
        context = self._analyze_betting_context(stage_actions)
        facing_all_in = context['facing_all_in']
        
        # Generate formatted action prompt
        action_prompt = f"The actions can be: {available_actions}. What should I do?"
        
        # Check if this is an all-in situation (either the player is facing all-in or went all-in themselves)
        # This covers both players who face others' all-ins and players who themselves went all-in
        is_all_in_situation = facing_all_in or player_stacks.get(player_perspective, default_stack) <= 0
        
        # If it's an all-in situation, adjust the action prompt to only include valid options
        if is_all_in_situation:
            # When facing an all-in, player can only fold or call the exact amount
            action_prompt = "The actions can be: ['fold', 'call']. What should I do?"
            # Add the call amount for clarity
            current_bet = self._get_current_bet(stage_actions, hand_id=hand_id)
            if current_bet > 0:
                action_prompt = f"The actions can be: ['fold', 'call']. What should I do? If I choose to \"call\", it will be for {current_bet}."
            
            # Return the prompt immediately, no bet sizing needed for all-in situations
            return prompt + action_prompt
        
        # Add bet sizing options if applicable (bet, raise, or re-raise actions available)
        # Only gets here if NOT an all-in situation
        bet_action_types = {"bet", "raise", "re-raise"} & set(available_actions)
        if bet_action_types:
            # Validate that we have only one betting action type (which is what we expect)
            if len(bet_action_types) > 1:
                # This should never happen based on poker rules
                raise ValueError(f"Hand {hand_id}: Multiple betting actions available simultaneously: {bet_action_types}. This violates poker rules.")
            
            # Get the appropriate action type for sizing options
            sizing_action = list(bet_action_types)[0]
            
            # Prepare game state for bet sizing options
            game_state = {
                'big_blind': float(blinds.split('/')[1].strip('$')),
                'pot_size': pot_value,
                'player_stack': player_stacks.get(player_perspective, default_stack),
                'current_bet': self._get_current_bet(
                    stages.get(stage, {}).get('actions', []), 
                    hand_id=hand_id
                )
            }
            
            # Add the winning action amount from the pokergpt_format
            if player_perspective == pokergpt_format.get('outcomes', {}).get('winner'):
                # Look for the amount associated with the winner's last action
                # Check all stages in reverse order to find the last action by the winner
                stage_order = ['river', 'turn', 'flop', 'preflop']
                for stage_name in stage_order:
                    if stage_name in stages and 'actions' in stages[stage_name]:
                        stage_actions = stages[stage_name]['actions']
                        # Look for the last action by this player that's a bet/raise/call
                        for action in reversed(stage_actions):
                            if action.get('player') == player_perspective:
                                action_type = action.get('action')
                                if action_type in ['bets', 'raises', 'calls'] and 'amount' in action:
                                    try:
                                        game_state['winning_amount'] = float(action['amount'])
                                        break
                                    except (ValueError, TypeError):
                                        pass
                        # If we found a winning amount, stop looking through stages
                        if 'winning_amount' in game_state:
                            break
            
            # Generate sizing options - don't catch exceptions here either
            # If we can't generate proper sizing options, we should fail and fix the issue
            sizing_options = self._generate_bet_sizing_options(
                sizing_action, 
                game_state,
                hand_id=hand_id
            )
            
            # Add sizing options to prompt if available
            if sizing_options:
                action_prompt += f" If I choose to \"{sizing_action}\", then how much? Choose a number from {sizing_options}."
        
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
        skipped_count = 0
        
        for hand in hands_data:
            # If we need actions but formatted_winning_action is missing, skip this hand
            if include_actions:
                winner = hand.get('winner')
                if winner and (not 'formatted_winning_action' in hand or not hand['formatted_winning_action']):
                    hand_id = hand.get('hand_id', 'unknown')
                    print(f"Warning: Hand {hand_id} missing formatted_winning_action. Skipping this hand.")
                    skipped_count += 1
                    continue
            
            # Get the prompt
            prompt = self.format_hand_to_pokergpt_prompt(hand)
            
            result = {'prompt': prompt}
            
            # Add the formatted winning action if needed
            if include_actions:
                winner = hand.get('winner')
                if winner and 'formatted_winning_action' in hand and hand['formatted_winning_action']:
                    result['action'] = hand['formatted_winning_action']
            
            formatted_data.append(result)
        
        if skipped_count > 0:
            print(f"Total hands skipped due to missing formatted_winning_action: {skipped_count}")
            
        return formatted_data