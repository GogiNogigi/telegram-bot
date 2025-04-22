import json
import os
from typing import List, Set

# Simple JSON-based database for subscribed users
DB_FILE = "subscribers.json"

def load_subscribers() -> Set[int]:
    """Load subscribers from the database file"""
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r') as f:
                data = json.load(f)
                return set(data.get('subscribers', []))
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading subscribers: {e}")
            return set()
    else:
        # Import default users from config if file doesn't exist
        from config import DEFAULT_USERS
        save_subscribers(set(DEFAULT_USERS))
        return set(DEFAULT_USERS)

def save_subscribers(subscribers: Set[int]) -> bool:
    """Save subscribers to the database file"""
    try:
        with open(DB_FILE, 'w') as f:
            json.dump({'subscribers': list(subscribers)}, f)
        return True
    except IOError as e:
        print(f"Error saving subscribers: {e}")
        return False

def add_subscriber(user_id: int) -> bool:
    """Add a new subscriber"""
    subscribers = load_subscribers()
    if user_id in subscribers:
        return False  # Already subscribed
    
    subscribers.add(user_id)
    return save_subscribers(subscribers)

def remove_subscriber(user_id: int) -> bool:
    """Remove a subscriber"""
    subscribers = load_subscribers()
    if user_id not in subscribers:
        return False  # Not subscribed
    
    subscribers.remove(user_id)
    return save_subscribers(subscribers)

def get_all_subscribers() -> List[int]:
    """Get all subscribers as a list"""
    return list(load_subscribers())
