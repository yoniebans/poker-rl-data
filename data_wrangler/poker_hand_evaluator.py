from typing import List, Tuple, Dict, Set, Optional
from collections import Counter


class PokerHandEvaluator:
    """
    Evaluates poker hands and provides accurate rankings for Texas Hold'em.
    """
    
    # Hand rankings from highest to lowest
    HAND_RANKS = [
        "Royal Flush",       # 9
        "Straight Flush",    # 8
        "Four of a Kind",    # 7
        "Full House",        # 6
        "Flush",             # 5
        "Straight",          # 4
        "Three of a Kind",   # 3
        "Two Pair",          # 2
        "Pair",              # 1
        "High Card"          # 0
    ]
    
    # Card values
    VALUES = {
        '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, 
        'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14
    }
    
    @classmethod
    def parse_card(cls, card: str) -> Tuple[str, str]:
        """
        Parse a card string into value and suit.
        
        Args:
            card: Card string (e.g., "Ah" for Ace of hearts)
        
        Returns:
            Tuple of (value, suit)
        """
        if len(card) < 2 or card == '**':
            return None, None
            
        value, suit = card[0], card[1]
        return value, suit
    
    @classmethod
    def evaluate_hand(cls, private_cards: List[str], community_cards: List[str]) -> Dict:
        """
        Evaluate a poker hand and return the ranking.
        
        Args:
            private_cards: List of private card strings
            community_cards: List of community card strings (can include placeholders)
        
        Returns:
            Dict with hand rank and other details
        """
        # Filter out placeholder cards
        valid_community = [c for c in community_cards if c != '**' and len(c) >= 2]
        
        # If we don't have enough cards for a full evaluation
        if len(private_cards) < 2 or (len(private_cards) + len(valid_community)) < 5:
            # Preflop evaluation based on private cards only
            if len(valid_community) == 0 and len(private_cards) == 2:
                return cls._evaluate_preflop(private_cards)
            # Partial evaluation based on available cards
            return cls._evaluate_partial(private_cards, valid_community)
        
        # Full evaluation with 5+ cards
        return cls._evaluate_full(private_cards, valid_community)
    
    @classmethod
    def _evaluate_preflop(cls, private_cards: List[str]) -> Dict:
        """
        Evaluate preflop hand strength based on private cards only.
        
        Args:
            private_cards: List of private card strings
        
        Returns:
            Dict with hand rank and details
        """
        if len(private_cards) != 2:
            return {"rank": "Unknown", "rank_index": -1}
            
        # Parse cards
        val1, suit1 = cls.parse_card(private_cards[0])
        val2, suit2 = cls.parse_card(private_cards[1])
        
        if val1 is None or val2 is None:
            return {"rank": "Unknown", "rank_index": -1}
            
        # Check for pair
        if val1 == val2:
            pair_rank = cls.VALUES.get(val1, 0)
            if pair_rank >= 10:  # TT or higher
                return {"rank": "High Pair", "rank_index": 1, "value": pair_rank}
            else:
                return {"rank": "Pair", "rank_index": 1, "value": pair_rank}
                
        # Get numeric values
        num_val1 = cls.VALUES.get(val1, 0)
        num_val2 = cls.VALUES.get(val2, 0)
        
        # Ensure val1 is higher
        if num_val2 > num_val1:
            num_val1, num_val2 = num_val2, num_val1
            val1, val2 = val2, val1
            suit1, suit2 = suit2, suit1
            
        # Check for high cards
        if num_val1 >= 12:  # Q or higher
            if num_val2 >= 10:  # T or higher
                return {"rank": "Strong High Cards", "rank_index": 0, "values": [num_val1, num_val2]}
            return {"rank": "High Card", "rank_index": 0, "values": [num_val1, num_val2]}
            
        # Check for suited
        suited = suit1 == suit2
        
        # Check for connected (straight potential)
        connected = abs(num_val1 - num_val2) <= 4
        
        if suited and connected:
            return {"rank": "Suited Connectors", "rank_index": 0, "values": [num_val1, num_val2]}
        elif suited:
            return {"rank": "Suited Cards", "rank_index": 0, "values": [num_val1, num_val2]}
        elif connected:
            return {"rank": "Connectors", "rank_index": 0, "values": [num_val1, num_val2]}
            
        # Default low cards
        return {"rank": "High Card", "rank_index": 0, "values": [num_val1, num_val2]}
    
    @classmethod
    def _evaluate_partial(cls, private_cards: List[str], community_cards: List[str]) -> Dict:
        """
        Perform a partial evaluation with incomplete community cards.
        
        Args:
            private_cards: List of private card strings
            community_cards: List of known community card strings
        
        Returns:
            Dict with best current hand rank and details
        """
        # Parse all available cards
        all_cards = private_cards + community_cards
        parsed_cards = []
        
        for card in all_cards:
            val, suit = cls.parse_card(card)
            if val is not None and suit is not None:
                parsed_cards.append((val, suit))
                
        if len(parsed_cards) < 3:
            return {"rank": "Incomplete", "rank_index": -1}
            
        # Count values and suits
        values = [v for v, s in parsed_cards]
        suits = [s for v, s in parsed_cards]
        
        value_counts = Counter(values)
        suit_counts = Counter(suits)
        
        # Check for current hand types
        # Pair
        if max(value_counts.values()) >= 2:
            pairs = [v for v, count in value_counts.items() if count >= 2]
            if len(pairs) >= 2:
                return {"rank": "Two Pair", "rank_index": 2}
            elif max(value_counts.values()) >= 3:
                return {"rank": "Three of a Kind", "rank_index": 3}
            else:
                return {"rank": "Pair", "rank_index": 1}
                
        # Flush potential
        flush_suit = None
        for suit, count in suit_counts.items():
            if count >= 3:  # Potential flush
                flush_suit = suit
                break
                
        if flush_suit:
            return {"rank": "Flush Draw", "rank_index": -1, "potential": "Flush"}
            
        # Straight potential
        numeric_values = sorted([cls.VALUES.get(v, 0) for v in values])
        gaps = 0
        for i in range(len(numeric_values) - 1):
            gap = numeric_values[i+1] - numeric_values[i] - 1
            gaps += max(0, gap)
            
        if gaps <= 2 and len(numeric_values) >= 3:
            return {"rank": "Straight Draw", "rank_index": -1, "potential": "Straight"}
            
        # Default to high card
        high_val = max(cls.VALUES.get(v, 0) for v in values)
        if high_val >= 12:  # Q or higher
            return {"rank": "High Card", "rank_index": 0, "value": high_val}
        else:
            return {"rank": "Low Card", "rank_index": 0, "value": high_val}
    
    @classmethod
    def _evaluate_full(cls, private_cards: List[str], community_cards: List[str]) -> Dict:
        """
        Perform a full evaluation of the best 5-card hand from all available cards.
        
        Args:
            private_cards: List of private card strings
            community_cards: List of community card strings
        
        Returns:
            Dict with final hand rank and details
        """
        # Parse all cards
        all_cards = []
        for card in private_cards + community_cards:
            val, suit = cls.parse_card(card)
            if val is not None and suit is not None:
                all_cards.append((val, suit))
                
        if len(all_cards) < 5:
            return {"rank": "Incomplete", "rank_index": -1}
            
        # Get all value and suit information
        values = [v for v, s in all_cards]
        suits = [s for v, s in all_cards]
        
        numeric_values = [cls.VALUES.get(v, 0) for v in values]
        value_counts = Counter(values)
        suit_counts = Counter(suits)
        
        # Check for flush
        flush_suit = None
        for suit, count in suit_counts.items():
            if count >= 5:
                flush_suit = suit
                break
                
        # Check for straight
        distinct_values = sorted(set(numeric_values), reverse=True)
        
        # Handle Ace low straight (A,2,3,4,5)
        if 14 in distinct_values and 2 in distinct_values and 3 in distinct_values and 4 in distinct_values and 5 in distinct_values:
            straight_high = 5
            has_straight = True
        else:
            has_straight = False
            straight_high = 0
            
            # Check normal straights
            for i in range(len(distinct_values) - 4):
                if distinct_values[i] - distinct_values[i + 4] == 4:
                    has_straight = True
                    straight_high = distinct_values[i]
                    break
                    
        # Determine the hand
        # Royal Flush
        if has_straight and flush_suit and straight_high == 14:
            return {"rank": "Royal Flush", "rank_index": 9}
            
        # Straight Flush
        if has_straight and flush_suit:
            return {"rank": "Straight Flush", "rank_index": 8, "high_card": straight_high}
            
        # Four of a Kind
        if 4 in value_counts.values():
            quads = [v for v, count in value_counts.items() if count == 4][0]
            return {"rank": "Four of a Kind", "rank_index": 7, "value": cls.VALUES.get(quads, 0)}
            
        # Full House
        if 3 in value_counts.values() and 2 in value_counts.values():
            trips = [v for v, count in value_counts.items() if count == 3][0]
            return {"rank": "Full House", "rank_index": 6, "trips": cls.VALUES.get(trips, 0)}
            
        # Special case: two sets of three of a kind
        if list(value_counts.values()).count(3) >= 2:
            trips = sorted([cls.VALUES.get(v, 0) for v, count in value_counts.items() if count == 3], reverse=True)
            return {"rank": "Full House", "rank_index": 6, "trips": trips[0], "pair": trips[1]}
            
        # Flush
        if flush_suit:
            flush_cards = [cls.VALUES.get(v, 0) for v, s in all_cards if s == flush_suit]
            high_card = max(flush_cards)
            return {"rank": "Flush", "rank_index": 5, "high_card": high_card}
            
        # Straight
        if has_straight:
            return {"rank": "Straight", "rank_index": 4, "high_card": straight_high}
            
        # Three of a Kind
        if 3 in value_counts.values():
            trips = [v for v, count in value_counts.items() if count == 3][0]
            return {"rank": "Three of a Kind", "rank_index": 3, "value": cls.VALUES.get(trips, 0)}
            
        # Two Pair
        if list(value_counts.values()).count(2) >= 2:
            pairs = sorted([cls.VALUES.get(v, 0) for v, count in value_counts.items() if count == 2], reverse=True)
            return {"rank": "Two Pair", "rank_index": 2, "high_pair": pairs[0], "low_pair": pairs[1]}
            
        # Pair
        if 2 in value_counts.values():
            pair = [v for v, count in value_counts.items() if count == 2][0]
            return {"rank": "Pair", "rank_index": 1, "value": cls.VALUES.get(pair, 0)}
            
        # High Card
        high_card = max(numeric_values)
        return {"rank": "High Card", "rank_index": 0, "value": high_card}
    
    @classmethod
    def get_hand_rank_name(cls, eval_result: Dict) -> str:
        """
        Get a standardized hand rank name from an evaluation result.
        
        Args:
            eval_result: Evaluation result dictionary
            
        Returns:
            Standardized hand rank name
        """
        rank_index = eval_result.get("rank_index", -1)
        if rank_index < 0:
            return eval_result.get("rank", "Unknown")
            
        if rank_index < len(cls.HAND_RANKS):
            return cls.HAND_RANKS[9 - rank_index]  # Convert to 0-9 scale from our 9-0 scale
            
        return eval_result.get("rank", "Unknown")