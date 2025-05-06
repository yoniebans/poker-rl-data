import os
import json
from dotenv import load_dotenv
from data_wrangler.export_to_hf import HuggingFaceExporter
from data_wrangler.pokergpt_formatter import PokerGPTFormatter
from data_wrangler.poker_hand_evaluator import PokerHandEvaluator

# Load environment variables
load_dotenv()

def filter_showdown_hands(db_connection):
    """
    Create a database view or query to filter for hands that went to showdown.
    This ensures we have actual private card data available.
    """
    import psycopg2
    
    conn = psycopg2.connect(db_connection)
    cursor = conn.cursor()
    
    # Create a view of hands that went to showdown
    cursor.execute("""
    CREATE OR REPLACE VIEW showdown_hands AS
    SELECT * FROM hand_histories
    WHERE has_showdown = TRUE 
    AND raw_text LIKE '%shows [%'  -- Ensures cards are visible in raw text
    """)
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print("Created view of showdown hands with visible cards")

def test_card_extraction(db_connection):
    """
    Test the card extraction functionality with a sample hand.
    """
    import psycopg2
    
    conn = psycopg2.connect(db_connection)
    cursor = conn.cursor()
    
    # Get a sample showdown hand
    cursor.execute("""
    SELECT hand_id, raw_text, pokergpt_format, winner
    FROM hand_histories
    WHERE has_showdown = TRUE 
    AND raw_text LIKE '%shows [%'
    LIMIT 1
    """)
    
    row = cursor.fetchone()
    if not row:
        print("No showdown hands found in database")
        return
        
    hand_id, raw_text, pokergpt_format_json, winner = row
    
    # Parse the JSON
    if isinstance(pokergpt_format_json, str):
        pokergpt_format = json.loads(pokergpt_format_json)
    else:
        pokergpt_format = pokergpt_format_json
    
    # Create a hand data dictionary
    hand_data = {
        'hand_id': hand_id,
        'raw_text': raw_text,
        'pokergpt_format': pokergpt_format,
        'winner': winner
    }
    
    # Test the card extraction
    formatter = PokerGPTFormatter()
    private_cards = formatter._extract_private_cards(hand_data, winner)
    
    print(f"Hand ID: {hand_id}")
    print(f"Winner: {winner}")
    print(f"Extracted private cards: {private_cards}")
    
    # Show card characteristics
    characteristics = formatter._get_card_characteristics(private_cards)
    print(f"Card characteristics: {characteristics}")
    
    # Test hand evaluation with a few community card scenarios
    community_cards_scenarios = [
        [],  # Preflop
        ['Ah', '7d', '2s'],  # Flop
        ['Ah', '7d', '2s', 'Kc'],  # Turn
        ['Ah', '7d', '2s', 'Kc', 'Qh']  # River
    ]
    
    print("\nHand evaluation tests:")
    for scenario in community_cards_scenarios:
        eval_result = PokerHandEvaluator.evaluate_hand(private_cards, scenario)
        stage_name = "Preflop" if not scenario else f"{'Flop' if len(scenario) == 3 else 'Turn' if len(scenario) == 4 else 'River'}"
        print(f"  {stage_name} ({scenario}): {eval_result['rank']}")
    
    # Show a complete prompt example
    prompt = formatter.format_hand_to_pokergpt_prompt(hand_data)
    
    print("\nGenerated PokerGPT prompt:")
    print("=" * 40)
    print(prompt)
    print("=" * 40)
    
    cursor.close()
    conn.close()

def export_showdown_hands_dataset(db_connection):
    """
    Export a dataset of showdown hands with proper card extraction and hand evaluation.
    """
    # Create the SQL query to filter for hands with showdown and visible cards
    filter_query = """
    has_showdown = TRUE 
    AND raw_text LIKE '%shows [%'
    AND EXISTS (
        SELECT 1 FROM players p
        WHERE 
            p.player_id = winner
            AND p.mbb_per_hour >= 200
            AND p.total_hands >= 50
    )
    """
    
    filter_description = """
    This dataset contains high-quality hands that went to showdown, allowing access to the 
    actual private cards of players. This ensures proper hand evaluation and more realistic
    decision contexts for the model. All hands are from players with a win rate of at least
    200 mbb/hour over at least 50 hands, representing skilled play.
    """
    
    # Initialize the exporter with proper formatting
    exporter = HuggingFaceExporter(db_connection)
    
    # Export the dataset
    dataset = exporter.export_dataset(
        filter_query=filter_query,
        dataset_name="pokergpt_showdown_hands",
        push_to_hub=False,
        filter_description=filter_description,
        win_rate_threshold=200,
        min_hands=50,
        include_pokergpt_format=True,
        include_actions=True
    )
    
    print(f"Exported {len(dataset)} showdown hands to dataset")
    
    # Print a sample if available
    if len(dataset) > 0:
        print("\nSample PokerGPT prompt from showdown hands:")
        print("-" * 40)
        print(dataset[0]['pokergpt_prompt'])
        
        if 'action' in dataset[0]:
            print("\nCorresponding action:")
            print(dataset[0]['action'])

def main():
    """
    Main function to demonstrate the updated PokerGPT components.
    """
    # Get database connection string from environment
    db_connection = os.environ.get("DB_CONNECTION")
    if not db_connection:
        print("Error: DB_CONNECTION environment variable not set")
        print("Please create a .env file with your database connection string")
        return
    
    print("Testing updated PokerGPT components...")
    
    # Create a view of showdown hands (optional)
    # filter_showdown_hands(db_connection)
    
    # Test the card extraction and hand evaluation
    print("\n1. Testing card extraction and hand evaluation:")
    test_card_extraction(db_connection)
    
    # Export a dataset of showdown hands
    print("\n2. Exporting dataset of showdown hands:")
    export_showdown_hands_dataset(db_connection)
    
    print("\nAll tests complete!")

if __name__ == "__main__":
    main()