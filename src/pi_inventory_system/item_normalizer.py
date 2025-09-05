# Module for normalizing item names with synonyms and fuzzy matching

from difflib import SequenceMatcher
import re


# Define item synonyms and base names
ITEM_SYNONYMS = {
    # Beef
    'ground beef': [
        'beef', 'ground meat'
    ],
    'beef short rib': [
        'short rib', 'short ribs', 'beef ribs', 'beef short ribs',
        'short rib beef', 'ribs'
    ],
    'steak': [
        'steaks', 'sirloin', 'ribeye',
        'new york strip', 'strip steak', 't-bone', 'porterhouse'
    ],
    
    # Chicken
    'chicken breast': [
        'breast', 'chicken breasts', 'breasts', 'chicken breast meat',
        'chicken breast fillet', 'chicken breast fillets', 'chicken filet',
        'chicken filets'
    ],
    'chicken tenders': [
        'tenders', 'chicken tender', 'chicken tenderloin', 'chicken tenderloins',
        'chicken strips', 'chicken strip', 'chicken fingers', 'chicken finger'
    ],
    'chicken nuggets': [
        'nuggets', 'chicken nugget'
    ],
    
    # Fish
    'white fish': [
        'whitefish', 'white fish fillet', 'white fish fillets', 'tilapia',
        'tilapia fillet', 'tilapia fillets'
    ],
    'salmon': [
        'salmon fillet', 'salmon fillets', 'salmon steak', 'salmon steaks',
        'salmon portion', 'salmon portions', 'salmon piece', 'salmon pieces'
    ],
    
    # Turkey
    'ground turkey': [
        'turkey', 'turkey meat', 'ground turkey meat', 'ground turkey breast'
    ],
    
    # Other
    'ice cream': [
        'icecream', 'vanilla ice cream', 'chocolate ice cream', 'strawberry ice cream',
        'ice-cream', 'ice cream tub', 'ice cream container',
        'ice cream carton', 'ice cream pint', 'ice cream quart'
    ]
}

def normalize_item_name(item_name, config_manager):
    """
    Normalize an item name by:
    1. Converting to lowercase
    2. Removing extra spaces
    3. Matching against known synonyms
    4. Using fuzzy matching for similar items
    """
    # Clean the input
    item_name = item_name.lower().strip()
    item_name = re.sub(r'\s+', ' ', item_name)
    
    # First try exact matches in synonyms
    for base_name, synonyms in ITEM_SYNONYMS.items():
        if item_name == base_name or item_name in synonyms:
            return base_name
    
    # Then try fuzzy matching
    best_match = None
    command_config = config_manager.get_command_config()
    best_ratio = command_config.get('similarity_threshold', 0.8)  # Minimum similarity threshold from config
    
    for base_name, synonyms in ITEM_SYNONYMS.items():
        # Check against base name
        ratio = SequenceMatcher(None, item_name, base_name).ratio()
        if ratio > best_ratio:
            best_match = base_name
            best_ratio = ratio
        
        # Check against synonyms
        for synonym in synonyms:
            ratio = SequenceMatcher(None, item_name, synonym).ratio()
            if ratio > best_ratio:
                best_match = base_name
                best_ratio = ratio
    
    return best_match if best_match else item_name

def get_item_synonyms(item_name, config_manager):
    """Get all synonyms for an item name."""
    item_name = normalize_item_name(item_name, config_manager)
    if item_name in ITEM_SYNONYMS:
        return [item_name] + ITEM_SYNONYMS[item_name]
    return [item_name]
