# The Shepherd's Guide

A Flask-based web application designed to make playing a [Circle of the Shepherd](https://www.dndbeyond.com/classes/3-druid#CircleoftheShepherd) Druid easier in D&D 5e. Quickly summon and manage your spirit totems and conjured creatures during gameplay.

## About Circle of the Shepherd

Druids of the Circle of the Shepherd commune with the spirits of nature, especially the spirits of beasts and fey. These shepherds use their Wild Shape to summon spirit totems (Bear, Hawk, Unicorn) that protect and aid their allies, and they excel at conjuring nature's creatures to fight alongside them.

## Features

- **Monster Browser**: Browse and search through SRD 5e monsters for conjuration spells
- **Filter by Challenge Rating**: Quickly find creatures that match your spell requirements
- **Summon Creatures**: Add creatures to your active summons with customizable stats
- **Mighty Summoner Support**: Automatically calculates bonus HP from the 6th-level Circle of the Shepherd feature (adds 2 HP per Hit Die to summoned creatures)
- **Track Multiple Summons**: Manage HP and stats for multiple summoned creatures simultaneously
- **Player Character Sheet**: Track your Shepherd Druid's stats and abilities
- **Session Persistence**: Your summoned creatures persist across page refreshes
- **Conjuring Spells Reference**: Quick access to spells like Conjure Animals, Conjure Woodland Beings, and more

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/GWilsonTinnin/shepherds-guide.git
   cd shepherds-guide
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install flask
   ```

4. Run the application:
   ```bash
   python app.py
   ```

5. Open your browser and navigate to `http://localhost:5000`

## Usage

### Browsing Monsters
- The home page displays all available SRD monsters
- Use the search box to filter by name
- Use the CR filter to find creatures of a specific Challenge Rating

### Summoning Creatures
1. Click "Summon" next to any creature
2. Set the quantity of creatures to summon
3. Enable "Mighty Summoner" if you have that Druid feature (adds 2 HP per Hit Die)
4. Customize any stats if needed
5. Click "Summon" to add them to your active summons

### Managing Summoned Creatures
- View all active summons on the Summoned Creatures page
- Update current HP as creatures take damage
- Remove creatures when they're dismissed or defeated

### Player Character Sheet
- Track your summoner's basic stats and abilities
- Quick reference during gameplay

## Project Structure

```
shepherds-guide/
├── app.py              # Flask application and routes
├── data/
│   ├── srd_5e_monsters.json  # Monster data
│   └── spells.json           # Conjuration spell data
├── static/
│   └── style.css       # Custom styles
├── templates/
│   ├── index.html      # Monster list page
│   ├── creature.html   # Individual creature details
│   ├── summon.html     # Summon configuration page
│   ├── summoned.html   # Active summons management
│   ├── spells.html     # Conjuring spells list
│   ├── spell_detail.html # Spell details with compatible creatures
│   └── player.html     # Player character sheet
└── README.md
```

## Technologies

- **Backend**: Python, Flask
- **Frontend**: HTML, Bootstrap 5
- **Data**: JSON (SRD 5e monster data)

## License

This project uses monster data from the D&D 5e System Reference Document (SRD), which is available under the Open Gaming License (OGL).

## Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change.
