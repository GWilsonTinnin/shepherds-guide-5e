/**
 * D&D Beyond Character Extractor Bookmarklet
 * 
 * This script extracts character data from a D&D Beyond character sheet page
 * and copies it to the clipboard in a format compatible with the Druid Summons app.
 * 
 * To use as a bookmarklet:
 * 1. Create a new bookmark in your browser
 * 2. Set the URL to: javascript:(function(){...minified code...})();
 * 3. Navigate to your D&D Beyond character sheet
 * 4. Click the bookmarklet to extract and copy character data
 */

(function() {
    'use strict';

    // Helper function to safely get text content
    function getText(selector, defaultValue = '') {
        const el = document.querySelector(selector);
        return el ? el.textContent.trim() : defaultValue;
    }

    // Helper function to get all matching elements' text
    function getAllText(selector) {
        return Array.from(document.querySelectorAll(selector)).map(el => el.textContent.trim());
    }

    // Helper function to parse numeric values
    function parseNumber(str, defaultValue = 0) {
        const num = parseInt(str.replace(/[^\d-]/g, ''), 10);
        return isNaN(num) ? defaultValue : num;
    }

    // Extract character ID from URL
    function getCharacterId() {
        const match = window.location.pathname.match(/\/characters\/(\d+)/);
        return match ? match[1] : null;
    }

    // Extract basic character info
    function extractBasicInfo() {
        return {
            name: getText('.ddbc-character-tidbits__heading h1, .ct-character-tidbits__heading h1'),
            race: getText('.ddbc-character-summary__race, .ct-character-summary__race'),
            background: getText('.ddbc-character-summary__background, .ct-character-summary__background'),
        };
    }

    // Extract classes and levels
    function extractClasses() {
        const classText = getText('.ddbc-character-summary__classes, .ct-character-summary__classes');
        const classes = [];
        
        if (classText) {
            // Parse format like "Druid 8 / Monk 1" or "Druid 8"
            const classMatches = classText.match(/([A-Za-z]+(?:\s+[A-Za-z]+)?)\s*(\d+)/g);
            if (classMatches) {
                classMatches.forEach(match => {
                    const parts = match.match(/([A-Za-z]+(?:\s+[A-Za-z]+)?)\s*(\d+)/);
                    if (parts) {
                        classes.push({
                            name: parts[1].trim(),
                            level: parseInt(parts[2], 10),
                            subclass: '', // Subclass requires deeper parsing
                            hit_die: getHitDie(parts[1].trim()),
                            spellcasting: getSpellcastingType(parts[1].trim())
                        });
                    }
                });
            }
        }
        
        return classes;
    }

    // Get hit die for a class
    function getHitDie(className) {
        const hitDice = {
            'Barbarian': 'd12',
            'Bard': 'd8',
            'Cleric': 'd8',
            'Druid': 'd8',
            'Fighter': 'd10',
            'Monk': 'd8',
            'Paladin': 'd10',
            'Ranger': 'd10',
            'Rogue': 'd8',
            'Sorcerer': 'd6',
            'Warlock': 'd8',
            'Wizard': 'd6'
        };
        return hitDice[className] || 'd8';
    }

    // Get spellcasting type for a class
    function getSpellcastingType(className) {
        const types = {
            'Barbarian': 'none',
            'Bard': 'full',
            'Cleric': 'full',
            'Druid': 'full',
            'Fighter': 'none',
            'Monk': 'none',
            'Paladin': 'half',
            'Ranger': 'half',
            'Rogue': 'none',
            'Sorcerer': 'full',
            'Warlock': 'pact',
            'Wizard': 'full'
        };
        return types[className] || 'none';
    }

    // Extract ability scores
    function extractAbilityScores() {
        const abilities = {};
        const abilityMapping = {
            'STR': 'strength',
            'DEX': 'dexterity',
            'CON': 'constitution',
            'INT': 'intelligence',
            'WIS': 'wisdom',
            'CHA': 'charisma'
        };

        // Try multiple selectors for ability scores
        // D&D Beyond 2024 redesign uses different class names
        const abilityElements = document.querySelectorAll(
            '.ddbc-ability-summary, .ct-ability-summary, ' +
            '.ct-quick-info__ability, .ddbc-quick-info__ability, ' +
            '[data-testid*="ability-score"], [class*="ability-score-box"]'
        );
        
        abilityElements.forEach(el => {
            // Find the ability abbreviation
            const abbrEl = el.querySelector(
                '.ddbc-ability-summary__abbr, .ct-ability-summary__abbr, ' +
                '.ddbc-ability-summary__heading .ddbc-ability-summary__abbr, ' +
                '[class*="ability-summary__abbr"], [class*="stat-abbr"], [class*="ability-label"]'
            );
            
            // IMPORTANT: In D&D Beyond:
            // - __secondary / __score contains the SCORE (e.g., 16)
            // - __primary / __modifier contains the MODIFIER (e.g., +3)
            // We want the score, not the modifier!
            
            // First try to get the score specifically
            let scoreEl = el.querySelector(
                '.ddbc-ability-summary__secondary, .ct-ability-summary__secondary, ' +
                '[class*="ability-summary__secondary"], [class*="ability-score__value"], ' +
                '[class*="score-value"], [class*="stat-score"]'
            );
            
            // If we found an element, check if it looks like a score (1-30) or a modifier (+X/-X)
            if (scoreEl) {
                const text = scoreEl.textContent.trim();
                // If it has a + or - sign, it's a modifier, not a score
                if (text.match(/^[+-]/)) {
                    scoreEl = null; // Reset and try other methods
                }
            }
            
            // If no score element found, look through all child elements
            if (!scoreEl) {
                const allElements = el.querySelectorAll('*');
                for (const candidate of allElements) {
                    // Skip if it has child elements (we want leaf nodes)
                    if (candidate.children.length > 0) continue;
                    
                    const text = candidate.textContent.trim();
                    // Score is typically a number between 1-30 without +/- sign
                    // Modifier would have +/- sign or be a small number that doesn't make sense as a score
                    if (/^\d{1,2}$/.test(text)) {
                        const num = parseInt(text, 10);
                        // Valid ability scores are 1-30
                        if (num >= 1 && num <= 30) {
                            // Check it's not the modifier by ensuring it's larger than typical modifiers
                            // Modifiers without signs would be 0-10 at most for normal characters
                            // But scores are typically 8-20 for most characters
                            // If num >= 8, it's likely a score
                            if (num >= 8) {
                                scoreEl = candidate;
                                break;
                            }
                        }
                    }
                }
            }
            
            if (abbrEl && scoreEl) {
                const abbr = abbrEl.textContent.trim().toUpperCase();
                const value = parseNumber(scoreEl.textContent);
                
                if (abilityMapping[abbr]) {
                    abilities[abilityMapping[abbr]] = value;
                }
            }
        });

        // Fallback: try to get from stat blocks or ability block patterns
        if (Object.keys(abilities).length < 6) {
            const statBlocks = document.querySelectorAll('[class*="ability-block"], [class*="stat-block"], [class*="ability-score"]');
            statBlocks.forEach(block => {
                const label = block.querySelector('[class*="label"], [class*="abbr"], [class*="name"]');
                const value = block.querySelector('[class*="value"], [class*="score"]');
                if (label && value) {
                    const abbr = label.textContent.trim().toUpperCase().substring(0, 3);
                    if (abilityMapping[abbr] && !abilities[abilityMapping[abbr]]) {
                        const num = parseNumber(value.textContent);
                        // Only use if it looks like a score (8-30) not a modifier
                        if (num >= 8 && num <= 30) {
                            abilities[abilityMapping[abbr]] = num;
                        }
                    }
                }
            });
        }
        
        // Final fallback: if we got modifiers instead of scores, convert them to approximate scores
        // D&D 5e ability scores range from 1-30, but typically 3-20 for player characters
        // Modifiers range from -5 to +10 (for scores 1-30)
        // If all values are small (between -5 and 10), they're likely modifiers not scores
        const values = Object.values(abilities);
        const allLikelyModifiers = values.length > 0 && values.every(v => v >= -5 && v <= 10);
        const noneLikelyScores = values.length > 0 && !values.some(v => v >= 8 && v <= 30);
        
        if (allLikelyModifiers || noneLikelyScores) {
            console.log('D&D Beyond Extractor: Detected modifiers instead of scores, converting...');
            console.log('Original values:', JSON.stringify(abilities));
            for (const key in abilities) {
                const modifier = abilities[key];
                // Convert modifier back to score using 5e PHB formula: 
                // modifier = floor((score - 10) / 2)
                // Solving for score: score = 10 + (modifier * 2)
                // This gives the lower bound of the score range for that modifier
                abilities[key] = 10 + (modifier * 2);
            }
            console.log('Converted to scores:', JSON.stringify(abilities));
        }

        return abilities;
    }

    // Extract HP
    function extractHP() {
        // Try multiple selectors
        let currentHP = 0, maxHP = 0, tempHP = 0;

        // Current HP
        const hpCurrent = document.querySelector('.ct-health-summary__hp-number, .ddbc-health-summary__hp-number, [class*="health"] [class*="current"]');
        if (hpCurrent) {
            currentHP = parseNumber(hpCurrent.textContent);
        }

        // Max HP
        const hpMax = document.querySelector('.ct-health-summary__hp-max, .ddbc-health-summary__hp-max, [class*="health"] [class*="max"]');
        if (hpMax) {
            maxHP = parseNumber(hpMax.textContent);
        }

        // Fallback: combined HP display like "45/52"
        const combinedHP = getText('.ct-status-summary-mobile__hp, .ddbc-combat-mobile__hp');
        if (combinedHP && combinedHP.includes('/')) {
            const parts = combinedHP.split('/');
            if (parts.length === 2) {
                currentHP = parseNumber(parts[0]);
                maxHP = parseNumber(parts[1]);
            }
        }

        // Temp HP
        const tempHPEl = document.querySelector('[class*="temp-hp"] [class*="value"], .ct-health-summary__hp-item--temp .ct-health-summary__hp-number');
        if (tempHPEl) {
            tempHP = parseNumber(tempHPEl.textContent);
        }

        return { current_hp: currentHP, max_hp: maxHP, temp_hp: tempHP };
    }

    // Extract AC
    function extractAC() {
        const acEl = document.querySelector('.ddbc-armor-class-box__value, .ct-armor-class-box__value, [class*="armor-class"] [class*="value"]');
        return acEl ? parseNumber(acEl.textContent) : 10;
    }

    // Extract Speed
    function extractSpeed() {
        const speedEl = document.querySelector('.ddbc-speed-box__box-value, .ct-speed-box__box-value, [class*="speed"] [class*="value"]');
        const speed = speedEl ? speedEl.textContent.trim() : '30';
        return speed.includes('ft') ? speed : speed + ' ft';
    }

    // Extract Proficiency Bonus
    function extractProficiencyBonus() {
        const profEl = document.querySelector('.ddbc-proficiency-bonus-box__value, .ct-proficiency-bonus-box__value, [class*="proficiency"] [class*="value"]');
        return profEl ? parseNumber(profEl.textContent) : 2;
    }

    // Extract class features (specifically for Shepherd Druid summoning)
    function extractClassFeatures(classes) {
        const features = {
            mighty_summoner: false,
            guardian_spirit: false,
            faithful_summons: false,
            bear_spirit_active: false
        };

        // Check Druid level for Shepherd features
        const druidClass = classes.find(c => c.name.toLowerCase() === 'druid');
        if (druidClass) {
            const level = druidClass.level;
            // These would need user confirmation or checking the features tab
            // For now, set based on level eligibility
            // Mighty Summoner at Druid 6
            // Guardian Spirit at Druid 10
            // Faithful Summons at Druid 14
        }

        // Try to detect features from the features/traits section
        const featuresText = document.body.innerText.toLowerCase();
        
        if (featuresText.includes('mighty summoner')) {
            features.mighty_summoner = true;
        }
        if (featuresText.includes('guardian spirit')) {
            features.guardian_spirit = true;
        }
        if (featuresText.includes('faithful summons')) {
            features.faithful_summons = true;
        }

        return features;
    }

    // Extract skills
    function extractSkills() {
        const skills = [];
        const skillElements = document.querySelectorAll('.ct-skills__item, .ddbc-skills__item, [class*="skill-item"]');
        
        skillElements.forEach(el => {
            const nameEl = el.querySelector('.ct-skills__col--skill, .ddbc-skills__col--skill, [class*="name"]');
            const profEl = el.querySelector('.ct-skills__col--proficiency, [class*="proficiency"]');
            
            if (nameEl) {
                const name = nameEl.textContent.trim();
                const isProficient = profEl && (profEl.classList.contains('ct-skills__col--proficient') || 
                                                profEl.querySelector('[class*="filled"]'));
                if (isProficient) {
                    skills.push(name);
                }
            }
        });
        
        return skills;
    }

    // Extract saving throw proficiencies
    function extractSavingThrows() {
        const saves = [];
        const saveElements = document.querySelectorAll('.ct-saving-throws-summary__ability, .ddbc-saving-throws-summary__ability');
        
        saveElements.forEach(el => {
            const nameEl = el.querySelector('.ct-saving-throws-summary__ability-name, .ddbc-saving-throws-summary__ability-name');
            const profEl = el.querySelector('.ct-saving-throws-summary__ability-modifier, [class*="proficient"]');
            
            // Check if proficient (usually has a different style or checkmark)
            if (nameEl && el.classList.contains('ct-saving-throws-summary__ability--proficient')) {
                saves.push(nameEl.textContent.trim().toLowerCase());
            }
        });
        
        return saves;
    }

    // Main extraction function
    function extractCharacter() {
        const characterId = getCharacterId();
        
        if (!characterId) {
            throw new Error('Could not find character ID. Make sure you are on a D&D Beyond character sheet page.');
        }

        const basicInfo = extractBasicInfo();
        const classes = extractClasses();
        const abilityScores = extractAbilityScores();
        const hp = extractHP();
        const classFeatures = extractClassFeatures(classes);
        const skills = extractSkills();
        const savingThrows = extractSavingThrows();

        // Calculate total level
        const totalLevel = classes.reduce((sum, c) => sum + c.level, 0);

        // Build character data object
        const characterData = {
            // Basic Info
            name: basicInfo.name,
            race: basicInfo.race,
            background: basicInfo.background,
            alignment: '', // Not easily extracted, keep existing
            experience: 0,
            
            // Classes (multiclass support)
            classes: classes,
            total_level: totalLevel,
            
            // Ability Scores
            ability_scores: abilityScores,
            
            // Combat Stats
            max_hp: hp.max_hp,
            current_hp: hp.current_hp,
            ac: extractAC(),
            speed: extractSpeed(),
            proficiency_bonus: extractProficiencyBonus(),
            inspiration: 0,
            
            // Proficiencies
            proficiencies: {
                armor: [],
                weapons: [],
                tools: [],
                saving_throws: savingThrows,
                skills: skills
            },
            
            // Class features for summoning
            class_features: classFeatures,
            
            // Preserve text fields
            features: '',
            equipment: '',
            
            // D&D Beyond sync metadata
            dndbeyond_sync: {
                character_id: characterId,
                character_url: window.location.href,
                last_sync: new Date().toISOString(),
                source: 'dndbeyond_bookmarklet'
            }
        };

        return characterData;
    }

    // Run extraction and copy to clipboard
    try {
        // Check if we're on a D&D Beyond character page
        if (!window.location.hostname.includes('dndbeyond.com') || 
            !window.location.pathname.includes('/characters/')) {
            alert('Please navigate to a D&D Beyond character sheet page first.\n\nExample: https://www.dndbeyond.com/characters/123456789');
            return;
        }

        const characterData = extractCharacter();
        const jsonString = JSON.stringify(characterData, null, 2);

        // Copy to clipboard
        navigator.clipboard.writeText(jsonString).then(() => {
            // Create success notification
            const notification = document.createElement('div');
            notification.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: #28a745;
                color: white;
                padding: 20px;
                border-radius: 8px;
                z-index: 999999;
                font-family: Arial, sans-serif;
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                max-width: 400px;
            `;
            notification.innerHTML = `
                <strong style="font-size: 16px;">✓ Character Data Copied!</strong>
                <p style="margin: 10px 0 0 0; font-size: 14px;">
                    <strong>${characterData.name}</strong><br>
                    ${characterData.classes.map(c => `${c.name} ${c.level}`).join(' / ')}<br>
                    <br>
                    Go to your Druid Summons app and click "Import from D&D Beyond" to paste this data.
                </p>
            `;
            document.body.appendChild(notification);

            // Remove notification after 8 seconds
            setTimeout(() => notification.remove(), 8000);
        }).catch(err => {
            // Fallback: show data in a prompt
            console.error('Clipboard write failed:', err);
            prompt('Copy this character data (Ctrl+A, Ctrl+C):', jsonString);
        });

    } catch (error) {
        alert('Error extracting character data:\n\n' + error.message);
        console.error('D&D Beyond Extractor Error:', error);
    }
})();
