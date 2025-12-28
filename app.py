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
    return render_template('summoned.html', summoned=summoned.values())

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
        if current_hp is not None:
            try:
                summoned[creature_id]['current_hp'] = int(current_hp)
            except ValueError:
                pass  # Ignore invalid input
            session['summoned'] = summoned
    return redirect(url_for('summoned_creatures'))

@app.route('/set_summoner_info', methods=['POST'])
def set_summoner_info():
    session['summoner_class'] = request.form.get('summoner_class', '')
    session['summoner_subclass'] = request.form.get('summoner_subclass', '')
    return redirect(url_for('index'))

@app.route('/player', methods=['GET', 'POST'])
def player():
    fields = [
        'name', 'race', 'class', 'subclass', 'level',
        'background', 'alignment', 'experience',
        'strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma',
        'max_hp', 'current_hp', 'ac', 'speed',
        'proficiency_bonus', 'inspiration',
        'skills', 'saving_throws', 'features', 'equipment', 'spells'
    ]
    if request.method == 'POST':
        for field in fields:
            session[field] = request.form.get(field, '')
    character = {field: session.get(field, '') for field in fields}
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
    return render_template('spell_detail.html', spell=spell, creatures=creatures)

if __name__ == '__main__':
    app.run(debug=True)
