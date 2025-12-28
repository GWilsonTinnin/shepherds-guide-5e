import os
import json
import re
import copy
from flask import Flask, render_template, request, redirect, url_for, session
from uuid import uuid4

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24).hex())

SRD_MONSTERS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'data', 'srd_5e_monsters.json'))
SPELLS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'data', 'spells.json'))
PLAYER_DATA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'data', 'player_data.json'))

# Default player data structure
DEFAULT_PLAYER_DATA = {
    "name": "",
    "race": "",
    "class": "",
    "subclass": "",
    "level": 1,
    "background": "",
    "alignment": "",
    "experience": 0,
    "strength": 10,
    "dexterity": 10,
    "constitution": 10,
    "intelligence": 10,
    "wisdom": 10,
    "charisma": 10,
    "max_hp": 0,
    "current_hp": 0,
    "ac": 10,
    "speed": "30 ft",
    "proficiency_bonus": 2,
    "inspiration": 0,
    "skills": "",
    "saving_throws": "",
    "features": "",
    "equipment": "",
    "spells": "",
    "class_features": {
        "mighty_summoner": False,
        "guardian_spirit": False,
        "faithful_summons": False,
        "bear_spirit_active": False
    }
}

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
        # Temp HP = 5 + druid level
        temp_hp = 5 + player.get('level', 1)
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
    """Display and update player character sheet, persisted to JSON file."""
    fields = [
        'name', 'race', 'class', 'subclass', 'level',
        'background', 'alignment', 'experience',
        'strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma',
        'max_hp', 'current_hp', 'ac', 'speed',
        'proficiency_bonus', 'inspiration',
        'skills', 'saving_throws', 'features', 'equipment', 'spells'
    ]
    
    # Class features that affect summoning
    class_feature_fields = ['mighty_summoner', 'guardian_spirit', 'faithful_summons']
    
    if request.method == 'POST':
        # Load existing data to preserve structure
        character = load_player_data()
        
        # Update basic fields
        for field in fields:
            value = request.form.get(field, '')
            # Convert numeric fields
            if field in ['level', 'experience', 'strength', 'dexterity', 'constitution', 
                        'intelligence', 'wisdom', 'charisma', 'max_hp', 'current_hp', 
                        'ac', 'proficiency_bonus', 'inspiration']:
                try:
                    value = int(value) if value else 0
                except ValueError:
                    value = 0
            character[field] = value
        
        # Update class features (checkboxes)
        for feature in class_feature_fields:
            character['class_features'][feature] = request.form.get(feature) == 'on'
        
        # Save to JSON file
        save_player_data(character)
        
        return redirect(url_for('player'))
    
    # Load character data from JSON file
    character = load_player_data()
    return render_template('player.html', character=character)

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
