import psycopg2
import os
import json
from dotenv import load_dotenv
import sys

# Load environment variables
load_dotenv()

def examine_hand(hand_id):
    try:
        conn = psycopg2.connect(os.environ.get('DB_CONNECTION'))
        cur = conn.cursor()
        
        # First, get the hand history data
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
                pot_total,
                winner_cards,
                winning_action,
                formatted_winning_action
            FROM hand_histories 
            WHERE hand_id = %s
        ''', (hand_id,))
        
        row = cur.fetchone()
        if not row:
            print(f"No hand found with ID {hand_id}")
            return
            
        pokergpt_format, raw_text, has_preflop, has_flop, has_turn, has_river, has_showdown, winner, blinds, pot_total, winner_cards, winning_action_original, formatted_winning_action = row
        
        # Also get the dataset record with prompt and winning action
        cur.execute('''
            SELECT 
                pokergpt_prompt, 
                winning_action
            FROM dataset_records 
            WHERE hand_id = %s
        ''', (hand_id,))
        
        dataset_row = cur.fetchone()
        if dataset_row:
            pokergpt_prompt, dataset_winning_action = dataset_row
        else:
            print(f"No dataset record found for hand ID {hand_id}")
            pokergpt_prompt, dataset_winning_action = None, None
        
        if isinstance(pokergpt_format, str):
            pokergpt_format = json.loads(pokergpt_format)
            
        print(f"======= Hand ID: {hand_id} =======")
        print(f"Winner: {winner}")
        print(f"Winner's Cards: {winner_cards}")
        print(f"Winning Action (Original): {winning_action_original}")
        print(f"Winning Action (Formatted): {formatted_winning_action}")
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
        
        # Save raw hand text and intermediate representation to files
        output_dir = os.path.join("ai_docs", "reference", "data_lifecycle_examples", "showdown")
        os.makedirs(output_dir, exist_ok=True)
        
        # Save raw text
        raw_path = os.path.join(output_dir, f"{hand_id}_raw.txt")
        with open(raw_path, "w") as f:
            f.write(raw_text)
        print(f"\nRaw hand text saved to: {raw_path}")
        
        # Save intermediate representation
        inter_path = os.path.join(output_dir, f"{hand_id}_inter.json")
        with open(inter_path, "w") as f:
            json.dump(pokergpt_format, f, indent=2)
        print(f"Intermediate representation saved to: {inter_path}")
        
        # Save final dataset representation
        if pokergpt_prompt and dataset_winning_action:
            final_data = {
                "prompt": pokergpt_prompt,
                "response": dataset_winning_action
            }
            final_path = os.path.join(output_dir, f"{hand_id}_final.json")
            with open(final_path, "w") as f:
                json.dump(final_data, f, indent=2)
            print(f"Final dataset representation saved to: {final_path}")
            
            # Save prompt as a separate pretty-printed text file
            prompt_path = os.path.join(output_dir, f"{hand_id}_prompt.txt")
            with open(prompt_path, "w") as f:
                f.write(pokergpt_prompt)
            print(f"Prompt saved to: {prompt_path}")
        
        print("\nRaw Text (first 500 chars):")
        print(raw_text[:500])
        
    except Exception as e:
        print(f"Error: {str(e)}")
        
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        hand_id = sys.argv[1]
    else:
        hand_id = "254798095787"  # Default problematic hand
    
    examine_hand(hand_id)