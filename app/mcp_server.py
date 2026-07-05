import json
import os
import uuid
from datetime import datetime
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("lost-and-found-portal")

DB_FILE = os.path.join(os.path.dirname(__file__), "items_db.json")

def load_db():
    if not os.path.exists(DB_FILE):
        return []
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2)

@mcp.tool()
def report_item(item_type: str, category: str, description: str, location: str, contact_email: str) -> str:
    """Report a lost or found item.

    Args:
        item_type: Either 'lost' or 'found'.
        category: Category of the item (e.g., Electronics, Keys, Wallet, Clothing).
        description: Distinguishing description details (color, brand, text on item, etc.).
        location: Where it was lost or found.
        contact_email: Email to reach the reporter.
    """
    db = load_db()
    item_id = str(uuid.uuid4())[:8]
    new_item = {
        "id": item_id,
        "item_type": item_type.lower(),
        "category": category,
        "description": description,
        "location": location,
        "contact_email": contact_email,
        "reported_at": datetime.now().isoformat(),
        "status": "active"
    }
    db.append(new_item)
    save_db(db)
    return f"Item reported successfully! Assigned ID: {item_id}. Match searches will run automatically."

@mcp.tool()
def search_items(query: str, category: str = None) -> str:
    """Search for reported items in the database by query terms and optional category.

    Args:
        query: Search keywords to match in description or location.
        category: Optional category filter.
    """
    db = load_db()
    results = []
    query_words = query.lower().split()

    for item in db:
        if item["status"] != "active":
            continue
        if category and item["category"].lower() != category.lower():
            continue

        # Match keywords in description or location
        desc_match = any(word in item["description"].lower() for word in query_words)
        loc_match = any(word in item["location"].lower() for word in query_words)

        if desc_match or loc_match or query.lower() in item["description"].lower():
            results.append(item)

    if not results:
        return "No matching active items found in database."

    return json.dumps(results, indent=2)

@mcp.tool()
def claim_item(item_id: str, claimant_email: str) -> str:
    """Claim a matched item in the database. Marks it as claimed.

    Args:
        item_id: The ID of the item being claimed.
        claimant_email: The contact email of the person claiming the item.
    """
    db = load_db()
    for item in db:
        if item["id"] == item_id:
            if item["status"] == "claimed":
                return f"Item {item_id} has already been claimed."
            item["status"] = "claimed"
            item["claimant_email"] = claimant_email
            item["claimed_at"] = datetime.now().isoformat()
            save_db(db)
            return f"Success! Item {item_id} has been claimed. Notification sent to reporter {item['contact_email']} and claimant {claimant_email}."

    return f"Error: Item ID {item_id} not found."

if __name__ == "__main__":
    mcp.run()
