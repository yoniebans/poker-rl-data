import psycopg2
import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def examine_hand(hand_id):
    try:
        conn = psycopg2.connect(os.environ.get('DB_CONNECTION'))
        cur = conn.cursor()
        
        # Get all the basic hand information
        cur.execute('''
            SELECT 
                pokergpt_format, 
                raw_text,
                has_preflop,
                has_flop,
                has_turn,
                has_river,
                has_showdown,
                winner,
                blinds,
                pot_total
            FROM hand_histories 
            WHERE hand_id = %s
        ''', (hand_id,))
        
        row = cur.fetchone()
        if not row:
            print(f"No hand found with ID {hand_id}")
            return
            
        pokergpt_format, raw_text, has_preflop, has_flop, has_turn, has_river, has_showdown, winner, blinds, pot_total = row
        
        if isinstance(pokergpt_format, str):
            pokergpt_format = json.loads(pokergpt_format)
            
        print(f"======= Hand ID: {hand_id} =======")
        print(f"Winner: {winner}")
        print(f"Blinds: {blinds}")
        print(f"Stored Pot Total: {pot_total}")
        print(f"Game stages: Preflop={has_preflop}, Flop={has_flop}, Turn={has_turn}, River={has_river}, Showdown={has_showdown}")
        
        # Gather players and their stacks/actions
        basic_info = pokergpt_format.get('basic_info', {})
        players = basic_info.get('players', [])
        
        print("\nPlayers:")
        for p in players:
            print(f"- {p.get('name')}: Stack={p.get('stack')}")
        
        # Check all actions to calculate pot manually
        stages = pokergpt_format.get('stages', {})
        
        print("\nStages and Actions:")
        total_pot = 0
        player_contributions = {}
        
        for stage_name, stage_data in stages.items():
            print(f"\n{stage_name.upper()}:")
            actions = stage_data.get('actions', [])
            
            for action in actions:
                player = action.get('player')
                action_type = action.get('action')
                amount = action.get('amount', 'N/A')
                
                print(f"- {player} {action_type} {amount}")
                
                # Track contributions to pot
                if action_type in ['calls', 'bets', 'raises'] and amount != 'N/A':
                    try:
                        amount_val = float(amount)
                        if player not in player_contributions:
                            player_contributions[player] = 0
                        player_contributions[player] += amount_val
                        total_pot += amount_val
                    except (ValueError, TypeError):
                        print(f"  Warning: Invalid amount '{amount}' for {player}'s {action_type}")
        
        print("\nCalculated Pot:")
        print(f"Total: {total_pot}")
        print("\nPlayer Contributions:")
        for player, amount in player_contributions.items():
            print(f"- {player}: {amount}")
        
        # Check how pot is calculated in our formatter
        print("\nPot Value According to Format_hand_to_pokergpt_prompt Calculation Logic:")
        
        print("\nRaw Text (first 500 chars):")
        print(raw_text[:500])
        
    except Exception as e:
        print(f"Error: {str(e)}")
        
    finally:
        if 'conn' in locals():
            conn.close()

# Examine the failing hand
examine_hand("254798095787")

# Also examine a successful hand for comparison
print("\n\n================= COMPARING WITH SUCCESSFUL HAND =================\n")
examine_hand("254799121066")  # This is the hand from the test output that worked