#!/usr/bin/env python3
import os
import psycopg2
import json
from dotenv import load_dotenv
from pprint import pprint

# Load environment variables
load_dotenv()

def analyze_non_showdown_winning_hands():
    """
    Identify and analyze hands that have a winning action but don't go to showdown.
    These are hands where someone won without cards being revealed.
    """
    # Get database connection from environment variable
    db_connection = os.environ.get("DB_CONNECTION")
    if not db_connection:
        print("Error: DB_CONNECTION environment variable not set")
        print("Please set your database connection string in .env file")
        return
    
    try:
        # Connect to the database
        conn = psycopg2.connect(db_connection)
        cursor = conn.cursor()
        
        # Count hands with winning action but no showdown
        cursor.execute("""
        SELECT COUNT(*) FROM hand_histories 
        WHERE winner IS NOT NULL 
        AND has_showdown = FALSE
        AND pokergpt_format::text LIKE '%"outcomes"%'
        """)
        non_showdown_winning_hands_count = cursor.fetchone()[0]
        
        # Count total hands with winning action
        cursor.execute("""
        SELECT COUNT(*) FROM hand_histories 
        WHERE winner IS NOT NULL 
        AND pokergpt_format::text LIKE '%"outcomes"%'
        """)
        all_winning_hands_count = cursor.fetchone()[0]
        
        # Get a sample of non-showdown winning hands
        cursor.execute("""
        SELECT 
            hand_id, 
            winner, 
            bb_won,
            has_preflop,
            has_flop,
            has_turn,
            has_river,
            pokergpt_format
        FROM hand_histories 
        WHERE winner IS NOT NULL 
        AND has_showdown = FALSE
        AND pokergpt_format::text LIKE '%"outcomes"%'
        LIMIT 5
        """)
        
        sample_hands = cursor.fetchall()
        
        # Analyze how far these hands progressed - simpler approach
        cursor.execute("""
        SELECT 
            stage_name, COUNT(*) as count
        FROM (
            SELECT 
                CASE 
                    WHEN has_river THEN 'river'
                    WHEN has_turn THEN 'turn'
                    WHEN has_flop THEN 'flop'
                    WHEN has_preflop THEN 'preflop'
                    ELSE 'unknown'
                END as stage_name
            FROM hand_histories 
            WHERE winner IS NOT NULL 
            AND has_showdown = FALSE
            AND pokergpt_format::text LIKE '%"outcomes"%'
        ) AS stages
        GROUP BY stage_name
        ORDER BY 
            CASE stage_name
                WHEN 'preflop' THEN 1
                WHEN 'flop' THEN 2
                WHEN 'turn' THEN 3
                WHEN 'river' THEN 4
                ELSE 5
            END
        """)
        
        stage_counts = cursor.fetchall()
        
        # Print results
        print("=== Analysis of Hands with Winning Action but No Showdown ===\n")
        print(f"Total hands with winning action: {all_winning_hands_count:,}")
        print(f"Hands with winning action but no showdown: {non_showdown_winning_hands_count:,} ({non_showdown_winning_hands_count/all_winning_hands_count*100:.2f}%)")
        
        print("\n--- Stage Distribution ---")
        for stage, count in stage_counts:
            print(f"Ended at {stage.upper()}: {count:,} hands ({count/non_showdown_winning_hands_count*100:.2f}%)")
        
        print("\n--- Sample Hands ---")
        for i, hand in enumerate(sample_hands):
            hand_id, winner, bb_won, has_preflop, has_flop, has_turn, has_river, pokergpt_format = hand
            
            if isinstance(pokergpt_format, str):
                pokergpt_format = json.loads(pokergpt_format)
            
            # Determine the last stage
            last_stage = "preflop"
            if has_river:
                last_stage = "river"
            elif has_turn:
                last_stage = "turn"
            elif has_flop:
                last_stage = "flop"
            
            # Extract just the relevant information from the hand
            relevant_info = {
                'hand_id': hand_id,
                'winner': winner,
                'bb_won': bb_won,
                'last_stage': last_stage,
                'winning_action': pokergpt_format.get('outcomes', {}).get('winning_action', {})
            }
            
            # Get the action that resulted in the win
            last_actions = []
            stages = pokergpt_format.get('stages', {})
            if last_stage in stages and 'actions' in stages[last_stage]:
                # Get the last actions in the final stage
                actions = stages[last_stage]['actions']
                if actions:
                    # Get the last 1-3 actions that led to the win
                    last_actions = actions[-min(3, len(actions)):]
            
            relevant_info['last_actions'] = last_actions
            
            print(f"\nHand #{i+1}: {hand_id}")
            print(f"Winner: {winner}")
            print(f"BB Won: {bb_won}")
            print(f"Last Stage: {last_stage.upper()}")
            
            if last_actions:
                print("Final Actions:")
                for action in last_actions:
                    player = action.get('player', 'Unknown')
                    action_type = action.get('action', 'Unknown')
                    amount = action.get('amount', '')
                    
                    action_str = f"  - {player}: {action_type}"
                    if amount:
                        action_str += f" {amount}"
                    print(action_str)
            
            # Try to find the winning action description
            winning_action = relevant_info['winning_action']
            if winning_action:
                print(f"Winning Action: {winner} {winning_action.get('action', '')} {winning_action.get('amount', '')}")
            
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Error during analysis: {e}")

if __name__ == "__main__":
    analyze_non_showdown_winning_hands()