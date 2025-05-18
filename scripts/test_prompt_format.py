#!/usr/bin/env python3
"""
Test script for the updated PokerGPT prompt formatting.
This script demonstrates the changes to the betting action types and bet sizing options.
"""

import os
import json
import psycopg2
from dotenv import load_dotenv
from data_wrangler.pokergpt_formatter import PokerGPTFormatter

# Load environment variables
load_dotenv()

def get_sample_hands(db_connection, limit=5):
    """
    Get a few sample hand histories for testing the prompt formatting
    """
    conn = psycopg2.connect(db_connection)
    cursor = conn.cursor()
    
    # Query for hands that went to different stages
    cursor.execute("""
    SELECT hand_id, raw_text, pokergpt_format, winner, 
           has_preflop, has_flop, has_turn, has_river, has_showdown
    FROM hand_histories
    WHERE pokergpt_format IS NOT NULL
    AND has_showdown = TRUE
    LIMIT %s
    """, (limit,))
    
    hands = []
    for row in cursor.fetchall():
        hand_id, raw_text, pokergpt_format_json, winner, has_preflop, has_flop, has_turn, has_river, has_showdown = row
        
        # Parse the JSON
        if isinstance(pokergpt_format_json, str):
            pokergpt_format = json.loads(pokergpt_format_json)
        else:
            pokergpt_format = pokergpt_format_json
        
        # Determine the game stage
        game_stage = "preflop"
        if has_river:
            game_stage = "river"
        elif has_turn:
            game_stage = "turn"
        elif has_flop:
            game_stage = "flop"
        
        # Create hand data dict
        hand_data = {
            'hand_id': hand_id,
            'raw_text': raw_text,
            'pokergpt_format': pokergpt_format,
            'winner': winner,
            'game_stage': game_stage,
            'has_preflop': has_preflop,
            'has_flop': has_flop,
            'has_turn': has_turn,
            'has_river': has_river,
            'has_showdown': has_showdown
        }
        
        hands.append(hand_data)
    
    cursor.close()
    conn.close()
    
    return hands

def test_prompts(hands):
    """
    Test the PokerGPT prompt formatting with the sample hands
    """
    formatter = PokerGPTFormatter()
    
    for i, hand in enumerate(hands):
        print(f"\n{'='*80}\nHAND {i+1}: {hand['hand_id']} - Stage: {hand['game_stage']}\n{'='*80}")
        
        try:
            # Format with the updated prompting
            prompt = formatter.format_hand_to_pokergpt_prompt(hand)
            
            # Check for the winner and their actions in the hand data
            winner = hand.get('winner')
            if winner:
                print(f"WINNER: {winner}")
                
                # Find winner's actions through stages
                stages = hand['pokergpt_format'].get('stages', {})
                stage_order = ['river', 'turn', 'flop', 'preflop']
                found_actions = []
                
                for stage_name in stage_order:
                    if stage_name in stages and 'actions' in stages[stage_name]:
                        stage_actions = stages[stage_name]['actions']
                        for action in reversed(stage_actions):
                            if action.get('player') == winner:
                                action_type = action.get('action')
                                if action_type in ['bets', 'raises', 'calls']:
                                    amount = action.get('amount', 'unknown')
                                    found_actions.append(f"{stage_name}: {action_type} {amount}")
                
                if found_actions:
                    print("WINNER ACTIONS:")
                    for action in found_actions:
                        print(f"  - {action}")
                else:
                    print("No betting actions found for winner")
            
            # Extract and display the action part for clarity
            # Print full prompt to inspect structure
            print("\nFULL PROMPT:")
            print(prompt)
            
            if "The pot value is" in prompt:
                action_part = prompt.split("The pot value is")[1]
                print("\nACTION PART:")
                print(action_part)
                
                # Check if the prompt includes bet sizing options
                if "Choose a number from" in action_part:
                    options_part = action_part.split("Choose a number from")[1]
                    print("\nBET SIZING OPTIONS:")
                    print(options_part)
                    
                    # Check if the winning amount is in the options
                    for action in found_actions:
                        if "unknown" not in action:
                            amount = action.split()[-1]
                            if amount in options_part:
                                print(f"SUCCESS: Winning amount {amount} is included in the options!")
                            else:
                                print(f"WARNING: Winning amount {amount} might not be in the options")
            else:
                print("\nNo action part found in prompt")
            
        except Exception as e:
            print(f"ERROR: {str(e)}")

def main():
    """
    Test the updated PokerGPT prompt formatting
    """
    # Get database connection string
    db_connection = os.environ.get("DB_CONNECTION")
    if not db_connection:
        print("Error: DB_CONNECTION environment variable not set")
        return
    
    # Get sample hands
    print("Fetching sample hands from database...")
    hands = get_sample_hands(db_connection)
    
    # Test the prompts
    print(f"Testing prompt formatting with {len(hands)} hands...")
    test_prompts(hands)

if __name__ == "__main__":
    main()