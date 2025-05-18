import psycopg2
import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_all_in_formats():
    """
    Check how PokerStars formats all-in situations in hand histories
    """
    try:
        conn = psycopg2.connect(os.environ.get('DB_CONNECTION'))
        cur = conn.cursor()
        
        # Find hands with "all-in" mentioned in the raw text
        cur.execute("""
            SELECT 
                hand_id, 
                raw_text
            FROM hand_histories 
            WHERE raw_text LIKE '%all-in%'
            LIMIT 200
        """)
        
        rows = cur.fetchall()
        
        print(f"Found {len(rows)} hands with all-in actions")
        print("\nExtracting all lines containing 'all-in':")
        
        for hand_id, raw_text in rows:
            print(f"\nHand ID: {hand_id}")
            # Extract all lines containing "all-in"
            all_in_lines = [line.strip() for line in raw_text.split('\n') 
                           if 'all-in' in line.lower()]
            
            for line in all_in_lines:
                print(f"- {line}")
                
    except Exception as e:
        print(f"Error: {str(e)}")
        
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    check_all_in_formats()