import os
import json
import re
import copy
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session
from uuid import uuid4

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24).hex())

SRD_MONSTERS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'data', 'srd_5e_monsters.json'))
SPELLS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'data', 'spells.json'))
PLAYER_DATA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'data', 'player_data.json'))

# Multiclassing prerequisites per 5e SRD
MULTICLASS_PREREQUISITES = {
    "Barbarian": {"strength": 13},
    "Bard": {"charisma": 13},
    "Cleric": {"wisdom": 13},
    "Druid": {"wisdom": 13},
    "Fighter": {"strength": 13},  # or dexterity 13
    "Monk": {"dexterity": 13, "wisdom": 13},
    "Paladin": {"strength": 13, "charisma": 13},
    "Ranger": {"dexterity": 13, "wisdom": 13},
    "Rogue": {"dexterity": 13},
    "Sorcerer": {"charisma": 13},
    "Warlock": {"charisma": 13},
    "Wizard": {"intelligence": 13}
}

# Spellcaster level multipliers for multiclass spell slot calculation
SPELLCASTER_MULTIPLIERS = {
    "full": 1,      # Bard, Cleric, Druid, Sorcerer, Wizard
    "half": 0.5,    # Paladin, Ranger
    "third": 0.34,  # Eldritch Knight Fighter, Arcane Trickster Rogue
    "none": 0
}

# Hit dice by class
CLASS_HIT_DICE = {
    "Barbarian": "d12",
    "Bard": "d8",
    "Cleric": "d8",
    "Druid": "d8",
    "Fighter": "d10",
    "Monk": "d8",
    "Paladin": "d10",
    "Ranger": "d10",
    "Rogue": "d8",
    "Sorcerer": "d6",
    "Warlock": "d8",
    "Wizard": "d6"
}

# Spellcasting type by class
CLASS_SPELLCASTING = {
    "Barbarian": "none",
    "Bard": "full",
    "Cleric": "full",
    "Druid": "full",
    "Fighter": "none",  # Eldritch Knight is third
    "Monk": "none",
    "Paladin": "half",
    "Ranger": "half",
    "Rogue": "none",  # Arcane Trickster is third
    "Sorcerer": "full",
    "Warlock": "pact",  # Special: Pact Magic
    "Wizard": "full"
}

# Multiclass spell slots table (caster level -> slots per level)
MULTICLASS_SPELL_SLOTS = {
    1:  [2, 0, 0, 0, 0, 0, 0, 0, 0],
    2:  [3, 0, 0, 0, 0, 0, 0, 0, 0],
    3:  [4, 2, 0, 0, 0, 0, 0, 0, 0],
    4:  [4, 3, 0, 0, 0, 0, 0, 0, 0],
    5:  [4, 3, 2, 0, 0, 0, 0, 0, 0],
    6:  [4, 3, 3, 0, 0, 0, 0, 0, 0],
    7:  [4, 3, 3, 1, 0, 0, 0, 0, 0],
    8:  [4, 3, 3, 2, 0, 0, 0, 0, 0],
    9:  [4, 3, 3, 3, 1, 0, 0, 0, 0],
    10: [4, 3, 3, 3, 2, 0, 0, 0, 0],
    11: [4, 3, 3, 3, 2, 1, 0, 0, 0],
    12: [4, 3, 3, 3, 2, 1, 0, 0, 0],
    13: [4, 3, 3, 3, 2, 1, 1, 0, 0],
    14: [4, 3, 3, 3, 2, 1, 1, 0, 0],
    15: [4, 3, 3, 3, 2, 1, 1, 1, 0],
    16: [4, 3, 3, 3, 2, 1, 1, 1, 0],
    17: [4, 3, 3, 3, 2, 1, 1, 1, 1],
    18: [4, 3, 3, 3, 3, 1, 1, 1, 1],
    19: [4, 3, 3, 3, 3, 2, 1, 1, 1],
    20: [4, 3, 3, 3, 3, 2, 2, 1, 1],
}

# Default player data structure with multiclass support
DEFAULT_PLAYER_DATA = {
    "name": "",
    "race": "",
    "background": "",
    "alignment": "",
    "experience": 0,
    "classes": [],  # List of {"name": "", "subclass": "", "level": 0, "hit_die": "", "spellcasting": "", "primary_ability": ""}
    "total_level": 0,
    "ability_scores": {
        "strength": 10,
        "dexterity": 10,
        "constitution": 10,
        "intelligence": 10,
        "wisdom": 10,
        "charisma": 10
    },
    "hit_dice": {},  # e.g., {"d8": 5, "d10": 3}
    "max_hp": 0,
    "current_hp": 0,
    "ac": 10,
    "speed": "30 ft",
    "proficiency_bonus": 2,
    "inspiration": 0,
    "spellcasting": {
        "spellcaster_level": 0,
        "spell_slots": {},
        "spells_known_by_class": {}
    },
    "proficiencies": {
        "armor": [],
        "weapons": [],
        "tools": [],
        "saving_throws": [],
        "skills": []
    },
    "features": "",
    "equipment": "",
    "class_features": {
        "mighty_summoner": False,
        "guardian_spirit": False,
        "faithful_summons": False,
        "bear_spirit_active": False
    },
    "dndbeyond_sync": {
        "character_id": None,
        "character_url": None,
        "last_sync": None,
        "source": "manual"
    }
}

def calculate_proficiency_bonus(total_level):
    """Calculate proficiency bonus based on total character level."""
    if total_level >= 17:
        return 6
    elif total_level >= 13:
        return 5
    elif total_level >= 9:
        return 4
    elif total_level >= 5:
        return 3
    else:
        return 2

def calculate_spellcaster_level(classes):
    """Calculate multiclass spellcaster level per 5e SRD rules."""
    total = 0
    for cls in classes:
        spellcasting = cls.get('spellcasting', CLASS_SPELLCASTING.get(cls.get('name', ''), 'none'))
        level = cls.get('level', 0)
        multiplier = SPELLCASTER_MULTIPLIERS.get(spellcasting, 0)
        total += level * multiplier
    return int(total)

def get_spell_slots(spellcaster_level):
    """Get spell slots for a given spellcaster level."""
    if spellcaster_level <= 0:
        return {}
    slots = MULTICLASS_SPELL_SLOTS.get(min(spellcaster_level, 20), [0]*9)
    result = {}
    level_names = ['1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th', '9th']
    for i, count in enumerate(slots):
        if count > 0:
            result[level_names[i]] = count
    return result

def calculate_hit_dice(classes):
    """Calculate total hit dice pool from all classes."""
    hit_dice = {}
    for cls in classes:
        die = cls.get('hit_die', CLASS_HIT_DICE.get(cls.get('name', ''), 'd8'))
        level = cls.get('level', 0)
        hit_dice[die] = hit_dice.get(die, 0) + level
    return hit_dice

def check_multiclass_prerequisites(ability_scores, class_name):
    """Check if ability scores meet prerequisites for a class."""
    prereqs = MULTICLASS_PREREQUISITES.get(class_name, {})
    for ability, minimum in prereqs.items():
        if ability_scores.get(ability, 0) < minimum:
            return False, f"{class_name} requires {ability.title()} {minimum}"
    return True, ""

def get_class_level(classes, class_name):
    """Get the level in a specific class."""
    for cls in classes:
        if cls.get('name', '').lower() == class_name.lower():
            return cls.get('level', 0)
    return 0

# Conjuring spells that summon creatures
CONJURE_SPELL_NAMES = [
    'Conjure Animals',
    'Conjure Minor Elementals',
    'Conjure Woodland Beings',
    'Conjure Celestial',
    'Conjure Elemental',
    'Conjure Fey',
    'Find Familiar',
    'Find Steed'
]

# Mapping of spells to the types of creatures they can summon
SPELL_CREATURE_MAPPINGS = {
    'Conjure Animals': {'cr_max': 2, 'types': ['beast']},
    'Conjure Minor Elementals': {'cr_max': 2, 'types': ['elemental']},
    'Conjure Woodland Beings': {'cr_max': 2, 'types': ['fey']},
    'Conjure Celestial': {'cr_max': 4, 'types': ['celestial']},
    'Conjure Elemental': {'cr_max': 5, 'types': ['elemental']},
    'Conjure Fey': {'cr_max': 6, 'types': ['fey', 'beast']},
    'Find Familiar': {'cr_max': 0, 'types': ['beast'], 'specific': ['Bat', 'Cat', 'Crab', 'Frog', 'Hawk', 'Lizard', 'Octopus', 'Owl', 'Poisonous Snake', 'Fish', 'Rat', 'Raven', 'Sea Horse', 'Spider', 'Weasel']},
    'Find Steed': {'cr_max': 2, 'types': ['beast'], 'specific': ['Warhorse', 'Pony', 'Camel', 'Elk', 'Mastiff']}
}

def load_srd_monsters():
    with open(SRD_MONSTERS_PATH, 'r') as f:
        return json.load(f)

def load_spells():
    with open(SPELLS_PATH, 'r') as f:
        return json.load(f)

def load_player_data():
    """Load player data from JSON file, creating it if it doesn't exist."""
    if os.path.exists(PLAYER_DATA_PATH):
        with open(PLAYER_DATA_PATH, 'r') as f:
            data = json.load(f)
            # Merge with defaults to ensure all fields exist
            merged = copy.deepcopy(DEFAULT_PLAYER_DATA)
            merged.update(data)
            # Ensure class_features dict is complete
            if 'class_features' in data:
                merged['class_features'] = copy.deepcopy(DEFAULT_PLAYER_DATA['class_features'])
                merged['class_features'].update(data.get('class_features', {}))
            return merged
    return copy.deepcopy(DEFAULT_PLAYER_DATA)

def save_player_data(data):
    """Save player data to JSON file."""
    with open(PLAYER_DATA_PATH, 'w') as f:
        json.dump(data, f, indent=4)

def get_player_class_features():
    """Get the player's active class features that affect summoning."""
    player = load_player_data()
    return player.get('class_features', {})

def get_conjure_spells():
    """Load and return only the conjuring/summoning spells."""
    spells = load_spells()
    return [spell for spell in spells if spell.get('name') in CONJURE_SPELL_NAMES]

def get_summonable_creatures(spell_name):
    """Get creatures that can be summoned by a specific spell."""
    if spell_name not in SPELL_CREATURE_MAPPINGS:
        return []
    
    mapping = SPELL_CREATURE_MAPPINGS[spell_name]
    monsters = load_srd_monsters()
    creatures = []
    
    # If specific creatures are listed, use those
    if 'specific' in mapping:
        specific_names = [n.lower() for n in mapping['specific']]
        for monster in monsters:
            if monster.get('name', '').lower() in specific_names:
                creatures.append(monster)
    else:
        # Filter by CR and type
        cr_max = mapping['cr_max']
        types = [t.lower() for t in mapping['types']]
        
        for monster in monsters:
            # Parse CR
            cr_str = str(monster.get('Challenge', '0'))
            try:
                if '/' in cr_str:
                    num, denom = cr_str.split('/')
                    cr = float(num) / float(denom)
                else:
                    cr = float(cr_str.split()[0])
            except:
                cr = 0
            
            # Check type from meta field
            meta = monster.get('meta', '').lower()
            is_valid_type = any(t in meta for t in types)
            
            if cr <= cr_max and is_valid_type:
                creatures.append(monster)
    
    return sorted(creatures, key=lambda x: x.get('name', ''))

def get_summoned():
    return session.setdefault('summoned', {})

def parse_hit_points(hit_points_str):
    hp_max_match = re.match(r'(\d+)', hit_points_str)
    dice_match = re.search(r'(\d+d\d+)', hit_points_str)
    hp_max = int(hp_max_match.group(1)) if hp_max_match else 0
    hit_dice = dice_match.group(1) if dice_match else ''
    return hp_max, hit_dice

@app.route('/')
def index():
    search_query = request.args.get('search', '').lower()
    cr_filter = request.args.get('cr', '')

    monsters = load_srd_monsters()
    if search_query:
        monsters = [m for m in monsters if search_query in m.get('name', '').lower()]
    if cr_filter:
        monsters = [m for m in monsters if str(m.get('Challenge', '')).startswith(cr_filter)]

    return render_template('index.html', creatures={m['name']: m for m in monsters}, search=search_query, cr=cr_filter)

@app.route('/creature/<name>')
def creature(name):
    monsters = load_srd_monsters()
    creature = next((m for m in monsters if m.get('name', '').lower() == name.lower()), None)
    if not creature:
        return "Creature not found", 404
    hp_max, hit_dice = parse_hit_points(creature.get('Hit Points', ''))
    return render_template('creature.html', name=name, creature=creature, hp_max=hp_max, hit_dice=hit_dice)

@app.route('/summon/<name>', methods=['GET', 'POST'])
def summon(name):
    monsters = load_srd_monsters()
    creature = next((m for m in monsters if m.get('name', '').lower() == name.lower()), None)
    if not creature:
        return "Creature not found", 404

    hp_str = creature.get('Hit Points', '')
    hp_max, hit_dice = parse_hit_points(hp_str)
    creature['hp_max'] = hp_max
    creature['hit_dice_value'] = hit_dice

    if request.method == 'POST':
        quantity = int(request.form.get('quantity', 1))
        mighty_summoner = request.form.get('mighty_summoner') == 'on'
        hp_str = request.form.get('Hit Points', creature.get('Hit Points', ''))
        hp_max, hit_dice = parse_hit_points(hp_str)
        creature['Hit Points'] = hp_str
        creature['hp_max'] = hp_max
        creature['hit_dice_value'] = hit_dice
        creature['Armor Class'] = request.form.get('Armor Class', creature.get('Armor Class', ''))
        for ability in ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA']:
            creature[ability] = request.form.get(ability, creature.get(ability, ''))

        extra_hp = 0
        if mighty_summoner and hit_dice:
            try:
                num_dice = int(hit_dice.split('d')[0])
                extra_hp = 2 * num_dice
            except Exception:
                extra_hp = 0

        summoned = get_summoned()
        for _ in range(quantity):
            creature_id = str(uuid4())
            creature_copy = copy.deepcopy(creature)
            base_hp = hp_max + extra_hp
            summoned[creature_id] = {
                'id': creature_id,
                'name': creature_copy['name'],
                'Hit Points': f"{base_hp} ({creature_copy.get('Hit Points', '')})",
                'HP Max': base_hp,
                'current_hp': base_hp,
                'Hit Dice': hit_dice,
                'Armor Class': creature_copy.get('Armor Class', ''),
                'STR': creature_copy.get('STR', ''),
                'DEX': creature_copy.get('DEX', ''),
                'CON': creature_copy.get('CON', ''),
                'INT': creature_copy.get('INT', ''),
                'WIS': creature_copy.get('WIS', ''),
                'CHA': creature_copy.get('CHA', ''),
                'abilities': {a: creature_copy.get(a, '') for a in ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA']},
                'skills': creature_copy.get('Skills', ''),
                'traits': creature_copy.get('Traits', ''),
                'actions': creature_copy.get('Actions', ''),
                'spells': creature_copy.get('Spells', ''),
                'equipment': creature_copy.get('Equipment', ''),
                'mighty_summoner': mighty_summoner,
                'extra_hp': extra_hp,
                'img_url': creature_copy.get('img_url', ''),
            }
        session['summoned'] = summoned
        return redirect(url_for('summoned_creatures'))

    return render_template('summon.html', name=name, creature=creature, saved=False)

@app.route('/summoned', methods=['GET', 'POST'])
def summoned_creatures():
    summoned = get_summoned()
    player = load_player_data()
    
    if request.method == 'POST':
        creature_id = request.form.get('id')
        new_hp = request.form.get('current_hp')
        if creature_id in summoned and new_hp is not None:
            # Update only the current HP, not the max HP string
            try:
                summoned[creature_id]['current_hp'] = int(new_hp)
            except ValueError:
                pass  # Ignore invalid input
            session['summoned'] = summoned
    
    return render_template('summoned.html', 
                          summoned=summoned.values(), 
                          player=player,
                          bear_spirit_active=player.get('class_features', {}).get('bear_spirit_active', False))

@app.route('/remove_summoned/<creature_id>', methods=['POST'])
def remove_summoned(creature_id):
    summoned = get_summoned()
    if creature_id in summoned:
        del summoned[creature_id]
        session['summoned'] = summoned
    return redirect(url_for('summoned_creatures'))

@app.route('/update_summoned/<creature_id>', methods=['POST'])
def update_summoned(creature_id):
    summoned = get_summoned()
    if creature_id in summoned:
        current_hp = request.form.get('current_hp')
        temp_hp = request.form.get('temp_hp')
        if current_hp is not None:
            try:
                summoned[creature_id]['current_hp'] = int(current_hp)
            except ValueError:
                pass  # Ignore invalid input
        if temp_hp is not None:
            try:
                summoned[creature_id]['temp_hp'] = int(temp_hp)
            except ValueError:
                summoned[creature_id]['temp_hp'] = 0
        session['summoned'] = summoned
    return redirect(url_for('summoned_creatures'))

@app.route('/toggle_bear_spirit', methods=['POST'])
def toggle_bear_spirit():
    """Toggle Bear Spirit aura on/off and apply temp HP to all summoned creatures."""
    player = load_player_data()
    bear_spirit_active = request.form.get('bear_spirit_active') == 'on'
    
    # Update player data
    player['class_features']['bear_spirit_active'] = bear_spirit_active
    save_player_data(player)
    
    # If activating bear spirit, apply temp HP to all summoned creatures
    if bear_spirit_active:
        summoned = get_summoned()
        # Temp HP = 5 + druid level (not total level per multiclass rules)
        druid_level = get_class_level(player.get('classes', []), 'Druid')
        temp_hp = 5 + druid_level
        for creature_id in summoned:
            # Only set temp HP if creature doesn't already have higher temp HP
            current_temp_hp = summoned[creature_id].get('temp_hp', 0)
            if temp_hp > current_temp_hp:
                summoned[creature_id]['temp_hp'] = temp_hp
        session['summoned'] = summoned
    
    return redirect(url_for('summoned_creatures'))

@app.route('/update_temp_hp/<creature_id>', methods=['POST'])
def update_temp_hp(creature_id):
    """Update temp HP for a specific creature."""
    summoned = get_summoned()
    if creature_id in summoned:
        temp_hp = request.form.get('temp_hp')
        if temp_hp is not None:
            try:
                summoned[creature_id]['temp_hp'] = max(0, int(temp_hp))
            except ValueError:
                summoned[creature_id]['temp_hp'] = 0
        session['summoned'] = summoned
    return redirect(url_for('summoned_creatures'))

@app.route('/set_summoner_info', methods=['POST'])
def set_summoner_info():
    session['summoner_class'] = request.form.get('summoner_class', '')
    session['summoner_subclass'] = request.form.get('summoner_subclass', '')
    return redirect(url_for('index'))

@app.route('/player', methods=['GET', 'POST'])
def player():
    """Display and update player character sheet with multiclass support, persisted to JSON file."""
    # Basic character fields
    basic_fields = ['name', 'race', 'background', 'alignment', 'experience', 'max_hp', 'current_hp', 'ac', 'speed', 'inspiration', 'features', 'equipment']
    ability_fields = ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma']
    
    # Class features that affect summoning
    class_feature_fields = ['mighty_summoner', 'guardian_spirit', 'faithful_summons']
    
    if request.method == 'POST':
        # Load existing data to preserve structure
        character = load_player_data()
        
        # Update basic fields
        for field in basic_fields:
            value = request.form.get(field, '')
            if field in ['experience', 'max_hp', 'current_hp', 'ac', 'inspiration']:
                try:
                    value = int(value) if value else 0
                except ValueError:
                    value = 0
            character[field] = value
        
        # Update ability scores
        if 'ability_scores' not in character:
            character['ability_scores'] = {}
        for ability in ability_fields:
            try:
                character['ability_scores'][ability] = int(request.form.get(ability, 10))
            except ValueError:
                character['ability_scores'][ability] = 10
        
        # Update class information (multiclass support)
        classes = []
        class_count = int(request.form.get('class_count', 1))
        for i in range(class_count):
            class_name = request.form.get(f'class_name_{i}', '')
            if class_name:
                try:
                    class_level = int(request.form.get(f'class_level_{i}', 1))
                except ValueError:
                    class_level = 1
                subclass = request.form.get(f'subclass_{i}', '')
                spellcasting = CLASS_SPELLCASTING.get(class_name, 'none')
                hit_die = CLASS_HIT_DICE.get(class_name, 'd8')
                
                classes.append({
                    'name': class_name,
                    'subclass': subclass,
                    'level': class_level,
                    'hit_die': hit_die,
                    'spellcasting': spellcasting,
                    'primary_ability': MULTICLASS_PREREQUISITES.get(class_name, {})
                })
        
        character['classes'] = classes
        
        # Calculate derived values
        character['total_level'] = sum(c.get('level', 0) for c in classes)
        character['proficiency_bonus'] = calculate_proficiency_bonus(character['total_level'])
        character['hit_dice'] = calculate_hit_dice(classes)
        
        # Calculate spellcasting
        spellcaster_level = calculate_spellcaster_level(classes)
        character['spellcasting'] = {
            'spellcaster_level': spellcaster_level,
            'spell_slots': get_spell_slots(spellcaster_level),
            'spells_known_by_class': character.get('spellcasting', {}).get('spells_known_by_class', {})
        }
        
        # Update class features (checkboxes)
        if 'class_features' not in character:
            character['class_features'] = {}
        for feature in class_feature_fields:
            character['class_features'][feature] = request.form.get(feature) == 'on'
        
        # Save to JSON file
        save_player_data(character)
        
        return redirect(url_for('player'))
    
    # Load character data from JSON file
    character = load_player_data()
    
    # Prepare multiclass validation info
    ability_scores = character.get('ability_scores', {})
    prereq_info = {}
    for class_name in MULTICLASS_PREREQUISITES:
        is_valid, message = check_multiclass_prerequisites(ability_scores, class_name)
        prereq_info[class_name] = {'valid': is_valid, 'message': message}
    
    return render_template('player.html', 
                          character=character, 
                          prereq_info=prereq_info,
                          class_hit_dice=CLASS_HIT_DICE,
                          class_spellcasting=CLASS_SPELLCASTING,
                          multiclass_prereqs=MULTICLASS_PREREQUISITES)

@app.route('/bookmarklet')
def bookmarklet():
    """Serve the D&D Beyond extractor bookmarklet code."""
    bookmarklet_code = '''javascript:(function(){'use strict';function e(e,t=''){const n=document.querySelector(e);return n?n.textContent.trim():t}function t(e,t=0){const n=parseInt(e.replace(/[^\\d-]/g,''),10);return isNaN(n)?t:n}function n(){const e=window.location.pathname.match(/\\/characters\\/(\\d+)/);return e?e[1]:null}function r(e){return{Barbarian:'d12',Bard:'d8',Cleric:'d8',Druid:'d8',Fighter:'d10',Monk:'d8',Paladin:'d10',Ranger:'d10',Rogue:'d8',Sorcerer:'d6',Warlock:'d8',Wizard:'d6'}[e]||'d8'}function a(e){return{Barbarian:'none',Bard:'full',Cleric:'full',Druid:'full',Fighter:'none',Monk:'none',Paladin:'half',Ranger:'half',Rogue:'none',Sorcerer:'full',Warlock:'pact',Wizard:'full'}[e]||'none'}function o(){const n=e('.ddbc-character-summary__classes, .ct-character-summary__classes'),o=[];if(n){const e=n.match(/([A-Za-z]+(?:\\s+[A-Za-z]+)?)\\s*(\\d+)/g);e&&e.forEach(e=>{const t=e.match(/([A-Za-z]+(?:\\s+[A-Za-z]+)?)\\s*(\\d+)/);t&&o.push({name:t[1].trim(),level:parseInt(t[2],10),subclass:'',hit_die:r(t[1].trim()),spellcasting:a(t[1].trim())})})}return o}function s(){const e={},n={STR:'strength',DEX:'dexterity',CON:'constitution',INT:'intelligence',WIS:'wisdom',CHA:'charisma'};return document.querySelectorAll('.ddbc-ability-summary, .ct-ability-summary, .ct-quick-info__ability, .ddbc-quick-info__ability').forEach(r=>{const a=r.querySelector('.ddbc-ability-summary__abbr, .ct-ability-summary__abbr'),o=r.querySelector('.ddbc-ability-summary__secondary, .ct-ability-summary__secondary, .ddbc-ability-summary__primary');if(a&&o){const r=a.textContent.trim().toUpperCase(),s=t(o.textContent);n[r]&&(e[n[r]]=s)}}),e}function c(){let n=0,r=0,a=0;const o=document.querySelector('.ct-health-summary__hp-number, .ddbc-health-summary__hp-number');o&&(n=t(o.textContent));const s=document.querySelector('.ct-health-summary__hp-max, .ddbc-health-summary__hp-max');s&&(r=t(s.textContent));const c=e('.ct-status-summary-mobile__hp, .ddbc-combat-mobile__hp');if(c&&c.includes('/')){const e=c.split('/');2===e.length&&(n=t(e[0]),r=t(e[1]))}const l=document.querySelector('[class*="temp-hp"] [class*="value"]');return l&&(a=t(l.textContent)),{current_hp:n,max_hp:r,temp_hp:a}}function l(){const e=document.querySelector('.ddbc-armor-class-box__value, .ct-armor-class-box__value');return e?t(e.textContent):10}function i(){const t=document.querySelector('.ddbc-speed-box__box-value, .ct-speed-box__box-value'),n=t?t.textContent.trim():'30';return n.includes('ft')?n:n+' ft'}function u(){const e=document.querySelector('.ddbc-proficiency-bonus-box__value, .ct-proficiency-bonus-box__value');return e?t(e.textContent):2}function d(e){const t={mighty_summoner:false,guardian_spirit:false,faithful_summons:false,bear_spirit_active:false},n=document.body.innerText.toLowerCase();return n.includes('mighty summoner')&&(t.mighty_summoner=true),n.includes('guardian spirit')&&(t.guardian_spirit=true),n.includes('faithful summons')&&(t.faithful_summons=true),t}try{if(!window.location.hostname.includes('dndbeyond.com')||!window.location.pathname.includes('/characters/'))return void alert('Please navigate to a D&D Beyond character sheet page first.');const t=n();if(!t)throw new Error('Could not find character ID.');const r=e('.ddbc-character-tidbits__heading h1, .ct-character-tidbits__heading h1'),a=e('.ddbc-character-summary__race, .ct-character-summary__race'),f=e('.ddbc-character-summary__background, .ct-character-summary__background'),m=o(),p=s(),_=c(),h=d(m),g={name:r,race:a,background:f,alignment:'',experience:0,classes:m,total_level:m.reduce((e,t)=>e+t.level,0),ability_scores:p,max_hp:_.max_hp,current_hp:_.current_hp,ac:l(),speed:i(),proficiency_bonus:u(),inspiration:0,proficiencies:{armor:[],weapons:[],tools:[],saving_throws:[],skills:[]},class_features:h,features:'',equipment:'',dndbeyond_sync:{character_id:t,character_url:window.location.href,last_sync:new Date().toISOString(),source:'dndbeyond_bookmarklet'}},b=JSON.stringify(g,null,2);navigator.clipboard.writeText(b).then(()=>{const e=document.createElement('div');e.style.cssText='position:fixed;top:20px;right:20px;background:#28a745;color:white;padding:20px;border-radius:8px;z-index:999999;font-family:Arial;box-shadow:0 4px 12px rgba(0,0,0,0.3);max-width:400px;';e.innerHTML='<strong>✓ Character Data Copied!</strong><p style="margin:10px 0 0;font-size:14px"><strong>'+g.name+'</strong><br>'+g.classes.map(e=>e.name+' '+e.level).join(' / ')+'<br><br>Go to your Druid Summons app and paste this data.</p>';document.body.appendChild(e);setTimeout(()=>e.remove(),8000)}).catch(e=>{prompt('Copy this character data:',b)})}catch(e){alert('Error: '+e.message)}})();'''
    return bookmarklet_code, 200, {'Content-Type': 'text/plain'}

@app.route('/import-character', methods=['POST'])
def import_character():
    """Import character data from D&D Beyond via JSON paste or API."""
    try:
        # Get JSON data from request
        if request.is_json:
            imported_data = request.get_json()
        else:
            # Try to parse from form data
            json_str = request.form.get('character_json', '')
            if not json_str:
                return json.dumps({'success': False, 'error': 'No character data provided'}), 400
            imported_data = json.loads(json_str)
        
        if not imported_data:
            return json.dumps({'success': False, 'error': 'Empty character data'}), 400
        
        # Load existing player data to preserve local-only fields
        existing_data = load_player_data()
        
        # Merge imported data with existing data
        # D&D Beyond data takes precedence for synced fields
        merged_data = copy.deepcopy(existing_data)
        
        # Update basic info
        for field in ['name', 'race', 'background', 'alignment']:
            if field in imported_data and imported_data[field]:
                merged_data[field] = imported_data[field]
        
        # Update classes (full replacement from D&D Beyond)
        if 'classes' in imported_data:
            merged_data['classes'] = imported_data['classes']
            # Recalculate derived values
            merged_data['total_level'] = sum(c.get('level', 0) for c in imported_data['classes'])
            merged_data['proficiency_bonus'] = calculate_proficiency_bonus(merged_data['total_level'])
            merged_data['hit_dice'] = calculate_hit_dice(imported_data['classes'])
            
            # Recalculate spellcasting
            spellcaster_level = calculate_spellcaster_level(imported_data['classes'])
            merged_data['spellcasting'] = {
                'spellcaster_level': spellcaster_level,
                'spell_slots': get_spell_slots(spellcaster_level),
                'spells_known_by_class': existing_data.get('spellcasting', {}).get('spells_known_by_class', {})
            }
        
        # Update ability scores
        if 'ability_scores' in imported_data:
            merged_data['ability_scores'] = imported_data['ability_scores']
        
        # Update combat stats
        for field in ['max_hp', 'current_hp', 'ac', 'speed', 'proficiency_bonus']:
            if field in imported_data:
                merged_data[field] = imported_data[field]
        
        # Update proficiencies
        if 'proficiencies' in imported_data:
            merged_data['proficiencies'] = imported_data['proficiencies']
        
        # Merge class features (preserve local toggles like bear_spirit_active)
        if 'class_features' in imported_data:
            if 'class_features' not in merged_data:
                merged_data['class_features'] = {}
            # Update from import but preserve bear_spirit_active if not in import
            bear_spirit = merged_data.get('class_features', {}).get('bear_spirit_active', False)
            merged_data['class_features'].update(imported_data['class_features'])
            if 'bear_spirit_active' not in imported_data.get('class_features', {}):
                merged_data['class_features']['bear_spirit_active'] = bear_spirit
        
        # Store D&D Beyond sync metadata
        if 'dndbeyond_sync' in imported_data:
            merged_data['dndbeyond_sync'] = imported_data['dndbeyond_sync']
        else:
            # Create sync metadata if not present
            merged_data['dndbeyond_sync'] = {
                'last_sync': datetime.now().isoformat(),
                'source': 'manual_import'
            }
        
        # Save merged data
        save_player_data(merged_data)
        
        return json.dumps({
            'success': True,
            'message': f"Successfully imported {merged_data.get('name', 'character')}",
            'character_name': merged_data.get('name', ''),
            'total_level': merged_data.get('total_level', 0)
        })
        
    except json.JSONDecodeError as e:
        return json.dumps({'success': False, 'error': f'Invalid JSON: {str(e)}'}), 400
    except Exception as e:
        return json.dumps({'success': False, 'error': str(e)}), 500

@app.route('/spells')
def spells():
    """Display conjuring/summoning spells with their summonable creatures."""
    conjure_spells = get_conjure_spells()
    # Sort by level
    level_order = {'cantrip': 0}
    conjure_spells.sort(key=lambda x: level_order.get(x.get('level', '0'), int(x.get('level', '0')) if x.get('level', '0').isdigit() else 0))
    return render_template('spells.html', spells=conjure_spells)

@app.route('/spell/<name>')
def spell_detail(name):
    """Display a specific spell with its summonable creatures."""
    spells = load_spells()
    spell = next((s for s in spells if s.get('name', '').lower() == name.lower()), None)
    if not spell:
        return "Spell not found", 404
    
    creatures = get_summonable_creatures(spell.get('name', ''))
    
    # Get filter parameters
    cr_filter = request.args.get('cr', '')
    skill_filter = request.args.get('skill', '')
    trait_filter = request.args.get('trait', '').lower()
    
    # Apply filters
    filtered_creatures = creatures
    
    if cr_filter:
        filtered_creatures = [c for c in filtered_creatures 
                            if str(c.get('Challenge', '')).split()[0] == cr_filter]
    
    if skill_filter:
        filtered_creatures = [c for c in filtered_creatures 
                            if skill_filter.lower() in c.get('Skills', '').lower()]
    
    if trait_filter:
        filtered_creatures = [c for c in filtered_creatures 
                            if trait_filter in c.get('Traits', '').lower()]
    
    # Extract unique CRs and skills for filter dropdowns
    available_crs = sorted(set(str(c.get('Challenge', '')).split()[0] for c in creatures if c.get('Challenge')),
                          key=lambda x: float(x) if '/' not in x else float(x.split('/')[0])/float(x.split('/')[1]))
    
    available_skills = set()
    for c in creatures:
        skill_str = c.get('Skills', '')
        if skill_str:
            for part in skill_str.split(','):
                skill_name = part.strip().split()[0] if part.strip() else ''
                if skill_name:
                    available_skills.add(skill_name)
    available_skills = sorted(available_skills)
    
    # Extract common traits
    available_traits = set()
    for c in creatures:
        traits = c.get('Traits', '')
        if traits:
            # Extract trait names (usually formatted as "Trait Name." at start of description)
            import re
            trait_names = re.findall(r'([A-Z][a-z]+(?: [A-Z][a-z]+)*)\\.', traits)
            available_traits.update(trait_names)
    available_traits = sorted(available_traits)
    
    return render_template('spell_detail.html', 
                          spell=spell, 
                          creatures=filtered_creatures,
                          total_creatures=len(creatures),
                          available_crs=available_crs,
                          available_skills=available_skills,
                          available_traits=available_traits,
                          current_cr=cr_filter,
                          current_skill=skill_filter,
                          current_trait=trait_filter)

if __name__ == '__main__':
    app.run(debug=True)
