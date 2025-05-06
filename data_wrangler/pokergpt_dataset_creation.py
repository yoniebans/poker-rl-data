# data_wrangler/pokergpt_dataset_creation.py
import os
import json
from dotenv import load_dotenv
from data_wrangler.export_to_hf import HuggingFaceExporter
from data_wrangler.pokergpt_formatter import PokerGPTFormatter

# Load environment variables including database connection string
load_dotenv()

def main():
    """
    Demonstrate the PokerGPT dataset creation workflow
    """
    # Get database connection string from environment
    db_connection = os.environ.get("DB_CONNECTION")
    if not db_connection:
        print("Error: DB_CONNECTION environment variable not set")
        print("Please create a .env file with your database connection string")
        return
    
    # Initialize the exporter
    exporter = HuggingFaceExporter(db_connection)
    
    print("Creating PokerGPT format dataset...")
    
    # Export a dataset with PokerGPT format prompts
    dataset = exporter.export_winning_player_dataset(
        min_win_rate=500,  # 500 mbb/h is a good threshold for skilled players
        min_hands=100,     # Ensure players have sufficient history
        dataset_name="pokergpt_training_data",
        push_to_hub=False,  # Set to True to push to HuggingFace Hub
        hub_name=None,      # Set to "your-username/dataset-name" for Hub
        include_pokergpt_format=True  # Include the formatted prompts
    )
    
    # Display statistics about the dataset
    print(f"Created dataset with {len(dataset)} examples")
    
    # Print a sample prompt
    if len(dataset) > 0:
        print("\nSample PokerGPT prompt:")
        print("-----------------------")
        print(dataset[0]['pokergpt_prompt'])
        
        # Print the corresponding action if available
        if 'action' in dataset[0]:
            print("\nWinning action:")
            print(dataset[0]['action'])
    
    # Demonstrate custom formatting
    print("\nDemonstrating custom formatting capabilities:")
    formatter = PokerGPTFormatter()
    
    # Get a single example
    example = {
        'pokergpt_format': dataset[0]['pokergpt_format'], 
        'winner': dataset[0]['winner']
    }
    
    # Format for different game stages
    stages = ['preflop', 'flop', 'turn', 'river']
    for stage in stages:
        try:
            prompt = formatter.format_hand_to_pokergpt_prompt(
                hand_data=example,
                stage=stage
            )
            
            # Print a short preview (first few lines)
            preview = "\n".join(prompt.split("\n")[:5]) + "\n..."
            print(f"\n{stage.upper()} stage prompt preview:")
            print(preview)
        except Exception as e:
            print(f"Stage {stage} not available in this hand: {e}")
    
    print("\nDataset creation complete!")
    print(f"Dataset saved to: pokergpt_training_data/")
    
    # Example of preparing for model training
    print("\nNext steps for training:")
    print("1. Load the dataset:")
    print("   from datasets import load_from_disk")
    print("   dataset = load_from_disk('pokergpt_training_data')")
    print("2. Format for training:")
    print("   train_data = [{'prompt': row['pokergpt_prompt'], 'completion': row['action']} for row in dataset]")
    print("3. Fine-tune your language model with this data")

if __name__ == "__main__":
    main()