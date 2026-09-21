import json
from typing import List, Dict, Any

SEED_SESSIONS: List[Dict[str, Any]] = [
    {
        "game": "Valorant",
        "title": "Ascendant Competitive - Haven Defensive Breakdown",
        "map_or_level": "Haven",
        "character_or_loadout": "Omen (Controller)",
        "outcome": "Defeat (10-13)",
        "duration_mins": 38,
        "timestamp": "2026-09-15T22:15:00",
        "stats": {
            "kda": "16/19/7",
            "acs": 218,
            "headshot_pct": 24,
            "first_bloods": 2,
            "first_deaths": 6,
            "clutch_rate": "1/4 (25%)"
        },
        "player_notes": "Kept getting picked early on C Long defense. I felt rushed and thought I could contest the angle before they set up, but Chamber was already holding with Operator. Got frustrated in the second half and started forcing duels.",
        "timeline": [
            {
                "timestamp_or_round": "Round 2 (Eco)",
                "event_type": "decision",
                "description": "Saved credits, played passive back of A site. Picked up enemy Vandal for next round.",
                "impact": "positive",
                "tilt_indicator": 1
            },
            {
                "timestamp_or_round": "Round 5 (Gun Round)",
                "event_type": "death",
                "description": "Died on C Long within 6 seconds. Dry-peeked without using Paranoia flash or waiting for Sova drone. Sniped by Chamber Operator.",
                "impact": "negative",
                "tilt_indicator": 4
            },
            {
                "timestamp_or_round": "Round 8 (Defense)",
                "event_type": "utility",
                "description": "Placed deep C Long smoke too late; enemy Jett dashed onto C site before smoke blossomed.",
                "impact": "negative",
                "tilt_indicator": 5
            },
            {
                "timestamp_or_round": "Round 11 (Clutch 1v2)",
                "event_type": "clutch",
                "description": "Executed Shrouded Step teleport onto Haven A Haven crate, won 1v2 clutch with calm crosshair placement.",
                "impact": "positive",
                "tilt_indicator": 2
            },
            {
                "timestamp_or_round": "Round 16 (Attack Side)",
                "event_type": "death",
                "description": "Pushed Garage without teammate flash support. Caught crossfire between Garage window and connector.",
                "impact": "negative",
                "tilt_indicator": 7
            },
            {
                "timestamp_or_round": "Round 19 (Tilt Spiral)",
                "event_type": "tilt",
                "description": "Bought Phantom without full armor due to impatience. Dry-peeked C Long again, died in first 8 seconds. Team lost site control.",
                "impact": "negative",
                "tilt_indicator": 9
            }
        ]
    },
    {
        "game": "Valorant",
        "title": "Diamond/Ascendant Duo - Ascent Tactical Masterclass",
        "map_or_level": "Ascent",
        "character_or_loadout": "Sova (Initiator)",
        "outcome": "Victory (13-8)",
        "duration_mins": 34,
        "timestamp": "2026-09-16T18:30:00",
        "stats": {
            "kda": "16/12/10",
            "acs": 232,
            "headshot_pct": 24,
            "first_bloods": 2,
            "first_deaths": 3,
            "clutch_rate": "1/3 (33%)"
        },
        "player_notes": "Felt completely in rhythm today. Pre-round recon dart lineups revealed B Main pushes every time. Communicated crossfires with Killjoy and never took 50-50 dry duels.",
        "timeline": [
            {
                "timestamp_or_round": "Round 3 (Defense)",
                "event_type": "utility",
                "description": "High B-main bounce recon arrow scanned 3 attackers. Wall-banged 1 through B lane with Odin.",
                "impact": "positive",
                "tilt_indicator": 0
            },
            {
                "timestamp_or_round": "Round 7 (Mid Control)",
                "event_type": "objective",
                "description": "Owl drone cleared Mid courtyard and Pizza. Secured Mid arch without taking damage.",
                "impact": "positive",
                "tilt_indicator": 1
            },
            {
                "timestamp_or_round": "Round 14 (Attack)",
                "event_type": "clutch",
                "description": "Hunter's Fury ultimate denied spike defuse from B Main lobby with 2 seconds remaining.",
                "impact": "positive",
                "tilt_indicator": 1
            },
            {
                "timestamp_or_round": "Round 18 (Defense Retake)",
                "event_type": "decision",
                "description": "Waited for full team regroup at CT spawn instead of solo tapping spike. Coordinated 4-man retake on A site.",
                "impact": "positive",
                "tilt_indicator": 1
            }
        ]
    },
    {
        "game": "Valorant",
        "title": "Late Night Solo Q - Haven Frustration & Tilt Spiral",
        "map_or_level": "Haven",
        "character_or_loadout": "Omen (Controller)",
        "outcome": "Defeat (8-13)",
        "duration_mins": 36,
        "timestamp": "2026-09-16T23:45:00",
        "stats": {
            "kda": "12/20/5",
            "acs": 172,
            "headshot_pct": 18,
            "first_bloods": 1,
            "first_deaths": 8,
            "clutch_rate": "0/3 (0%)"
        },
        "player_notes": "Should have logged off after Ascent. It was past 11:30 PM and my reaction time was completely shot. I made the exact same mistake as yesterday: contesting Haven C Long without utility and giving away free opening picks.",
        "timeline": [
            {
                "timestamp_or_round": "Round 3 (Defense)",
                "event_type": "death",
                "description": "Dry-peeked C Long again with Vandal. Opponent Jett had Operator. First death of the round at 0:14.",
                "impact": "negative",
                "tilt_indicator": 6
            },
            {
                "timestamp_or_round": "Round 6 (Defense)",
                "event_type": "utility",
                "description": "Smoked Garage but stepped into own smoke without sound cue, died to shotgun blast.",
                "impact": "negative",
                "tilt_indicator": 7
            },
            {
                "timestamp_or_round": "Round 9 (Tilt Event)",
                "event_type": "tilt",
                "description": "After losing round 8, held W key down A Long with zero team coordination. Headshotted immediately.",
                "impact": "negative",
                "tilt_indicator": 9
            },
            {
                "timestamp_or_round": "Round 15 (Attack)",
                "event_type": "decision",
                "description": "Rushed spike plant on B site while two defenders were still alive in A Link. Traded instantly.",
                "impact": "negative",
                "tilt_indicator": 8
            }
        ]
    },
    {
        "game": "Valorant",
        "title": "Ranked Trio - Bind Strategic Teleporter Control",
        "map_or_level": "Bind",
        "character_or_loadout": "Brimstone (Controller)",
        "outcome": "Victory (13-11)",
        "duration_mins": 42,
        "timestamp": "2026-09-17T19:15:00",
        "stats": {
            "kda": "18/14/11",
            "acs": 235,
            "headshot_pct": 22,
            "first_bloods": 3,
            "first_deaths": 2,
            "clutch_rate": "2/4 (50%)"
        },
        "player_notes": "Very disciplined game. Kept my molly for post-plant delay instead of throwing it early for chip damage. Rotated patiently through hookah.",
        "timeline": [
            {
                "timestamp_or_round": "Round 4 (Attack)",
                "event_type": "utility",
                "description": "Tri-smoke executed on B site (Elbow, CT, Hall) allowed safe spike plant without taking sniper fire.",
                "impact": "positive",
                "tilt_indicator": 0
            },
            {
                "timestamp_or_round": "Round 12 (Post-Plant)",
                "event_type": "clutch",
                "description": "Used incendiary molly lineup from B Fountain to burn 7 seconds off defuse clock, winning round.",
                "impact": "positive",
                "tilt_indicator": 1
            },
            {
                "timestamp_or_round": "Round 17 (Defense)",
                "event_type": "decision",
                "description": "Heard heavy footsteps outside A Short. Held fire until teammate flashed, converting an easy double kill.",
                "impact": "positive",
                "tilt_indicator": 1
            }
        ]
    },
    {
        "game": "Elden Ring",
        "title": "Stormhill Castle Approach - Margit Encounter Attempt 1",
        "map_or_level": "Margit the Fell Omen",
        "character_or_loadout": "Vagabond (Level 22, Claymore +2, Brass Shield)",
        "outcome": "Defeat (Boss at 18% HP)",
        "duration_mins": 14,
        "timestamp": "2026-09-16T15:10:00",
        "stats": {
            "boss_health_remaining": "18%",
            "stamina_exhaustion_count": 4,
            "panic_roll_count": 7,
            "parry_success_rate": "0/2 (0%)",
            "estus_flasks_used": "4/4"
        },
        "player_notes": "Had him so close to dead! In phase 2 I got greedy when his health dropped under 20%. I spammed light attacks, burned all my stamina, and then panic-rolled early when he charged his cane overhead slam. Got caught at the end of roll frames.",
        "timeline": [
            {
                "timestamp_or_round": "0:45 (Phase 1)",
                "event_type": "combat",
                "description": "Successfully baited Margit's jumping staff slam and landed two heavy jumping attacks.",
                "impact": "positive",
                "tilt_indicator": 1
            },
            {
                "timestamp_or_round": "1:30 (Stamina Misplay)",
                "event_type": "death",
                "description": "Blocked three consecutive golden dagger strikes with shield. Guard broken due to zero stamina recovery buffer.",
                "impact": "negative",
                "tilt_indicator": 4
            },
            {
                "timestamp_or_round": "2:40 (Phase 2 Transition)",
                "event_type": "combat",
                "description": "Dodged golden hammer sweep cleanly by rolling forward-left into his blind spot.",
                "impact": "positive",
                "tilt_indicator": 2
            },
            {
                "timestamp_or_round": "3:25 (Greed & Panic Roll)",
                "event_type": "tilt",
                "description": "Boss at 18% HP. Queued 3rd R1 attack instead of stepping back. Ran out of stamina. Panic rolled 0.3s too early on delayed cane slam, taking 650 lethal damage.",
                "impact": "negative",
                "tilt_indicator": 8
            }
        ]
    },
    {
        "game": "Elden Ring",
        "title": "Margit Retrial - Frustration & Aggressive Tilt Run",
        "map_or_level": "Margit the Fell Omen",
        "character_or_loadout": "Vagabond (Level 23, Claymore +3, Brass Shield)",
        "outcome": "Defeat (Boss at 75% HP)",
        "duration_mins": 6,
        "timestamp": "2026-09-16T15:28:00",
        "stats": {
            "boss_health_remaining": "75%",
            "stamina_exhaustion_count": 3,
            "panic_roll_count": 5,
            "parry_success_rate": "0/0",
            "estus_flasks_used": "3/4"
        },
        "player_notes": "Terrible run. Was still irritated about throwing the last attempt at 18% HP. Charged in aggressively without waiting for his attack animations to resolve, ate two quick daggers immediately.",
        "timeline": [
            {
                "timestamp_or_round": "0:20 (Opening)",
                "event_type": "tilt",
                "description": "Ran straight at boss on entry. Margit threw double holy daggers, staggered player out of heavy swing.",
                "impact": "negative",
                "tilt_indicator": 6
            },
            {
                "timestamp_or_round": "0:55 (Death)",
                "event_type": "death",
                "description": "Chugged healing flask directly in front of Margit without spacing. Punished with staff sweep, died in under 60 seconds.",
                "impact": "negative",
                "tilt_indicator": 9
            }
        ]
    },
    {
        "game": "Elden Ring",
        "title": "Margit Conquest - Disciplined Stamina & Delayed Roll Victory",
        "map_or_level": "Margit the Fell Omen",
        "character_or_loadout": "Vagabond (Level 24, Claymore +3, Brass Shield)",
        "outcome": "Victory (Boss Defeated)",
        "duration_mins": 12,
        "timestamp": "2026-09-16T16:05:00",
        "stats": {
            "boss_health_remaining": "0% (Defeated)",
            "stamina_exhaustion_count": 0,
            "panic_roll_count": 1,
            "parry_success_rate": "1/1 (100%)",
            "estus_flasks_used": "2/4"
        },
        "player_notes": "Took a 20-minute break to clear my head. Came back with a strict mental rule: count 2 beats before rolling on delayed overhead attacks, and NEVER drop stamina below 25%. Executed flawlessly.",
        "timeline": [
            {
                "timestamp_or_round": "1:15 (Delayed Roll Execution)",
                "event_type": "decision",
                "description": "Margit held overhead cane pose for 1.8s. Waited patiently, rolled exactly at downward swing release frame, completely avoiding damage.",
                "impact": "positive",
                "tilt_indicator": 0
            },
            {
                "timestamp_or_round": "2:30 (Stagger & Riposte)",
                "event_type": "combat",
                "description": "Landed 2 jumping heavy attacks to break Margit's poise. Landed critical strike for 420 damage.",
                "impact": "positive",
                "tilt_indicator": 1
            },
            {
                "timestamp_or_round": "3:40 (Clutch Finish)",
                "event_type": "clutch",
                "description": "Boss at 15% HP: Resisted temptation to spam light attacks. Kept distance, punished hammer landing with safe rolling poke to claim victory.",
                "impact": "positive",
                "tilt_indicator": 0
            }
        ]
    },
    {
        "game": "Apex Legends",
        "title": "Ranked Platinum Lobby - World's Edge Choke Trap",
        "map_or_level": "World's Edge",
        "character_or_loadout": "Bloodhound (R-301 Carbine & Peacekeeper)",
        "outcome": "4th Place (5 Kills, 1280 Dmg)",
        "duration_mins": 21,
        "timestamp": "2026-09-17T21:00:00",
        "stats": {
            "placement": "4th / 20",
            "kills": 5,
            "damage": 1280,
            "scans_used": 11,
            "third_partied_deaths": 1
        },
        "player_notes": "Won the early skirmish in Fragment East cleanly. Later in ring 3, we rotated through the narrow choke between Capitol and Harvester without using Eye of the Allfather scan first. Walked straight into a caustic trap and got third-partied from behind.",
        "timeline": [
            {
                "timestamp_or_round": "Ring 1 (Fragment Skirmish)",
                "event_type": "combat",
                "description": "Popped Beast of the Hunt ultimate, knocked 2 players in building zipper fight using Peacekeeper.",
                "impact": "positive",
                "tilt_indicator": 0
            },
            {
                "timestamp_or_round": "Ring 2 (Looting Transition)",
                "event_type": "decision",
                "description": "Spent 90 seconds excess time looting death boxes in the open instead of taking high ground early.",
                "impact": "neutral",
                "tilt_indicator": 2
            },
            {
                "timestamp_or_round": "Ring 3 (Choke Ambush)",
                "event_type": "death",
                "description": "Pushed through tight valley choke into Harvester without scanning ahead. Hit Caustic gas barrel, team pinned by sniper fire, eliminated by 3rd party squad from behind.",
                "impact": "negative",
                "tilt_indicator": 6
            }
        ]
    },
    {
        "session_id": "18",
        "game": "Valorant",
        "title": "Session #18: Valorant Ranked on Ascent",
        "date": "2026-09-17T20:00:00",
        "timestamp": "2026-09-17T20:00:00",
        "duration": "72 minutes",
        "duration_mins": 72,
        "score": "18/10",
        "kills": 18,
        "deaths": 10,
        "assists": 6,
        "result": "Win",
        "outcome": "Win",
        "map": "Ascent",
        "map_or_level": "Ascent",
        "configuration": "Phantom + preferred sensitivity",
        "character_or_loadout": "Phantom + preferred sensitivity",
        "performance_metrics": {
            "kd": 1.8,
            "acs": 285,
            "headshot_pct": 32,
            "first_bloods": 5,
            "duel_win_pct": 74
        },
        "stats": {
            "kda": "18/10/6",
            "acs": 285,
            "headshot_pct": 32,
            "first_bloods": 5
        },
        "player_notes": "Felt completely locked in. Sensitivity tweak was perfect, crosshair didn't jitter once. Won opening duels and held Ascent B site cleanly.",
        "ai_summary": "Strong performance session. Player achieved a 1.8 K/D and won the match while using their preferred configuration.",
        "ai_insights": [
            "Phantom + preferred sensitivity yielded peak 1.8 K/D duel conversion rate.",
            "Ascent mid-round discipline minimized first deaths and maximized team retakes.",
            "72-minute session was optimal duration before any cognitive fatigue onset."
        ],
        "timeline": [
            {
                "timestamp_or_round": "Round 4 (Buy Round)",
                "event_type": "combat",
                "description": "Clean double kill on Ascent B main defense using Phantom recoil reset.",
                "impact": "positive",
                "tilt_indicator": 0
            },
            {
                "timestamp_or_round": "Round 9 (Mid Hold)",
                "event_type": "decision",
                "description": "Held Pizza angle patiently with preferred sensitivity; punished Catwalk push.",
                "impact": "positive",
                "tilt_indicator": 0
            },
            {
                "timestamp_or_round": "Round 16 (Clutch)",
                "event_type": "clutch",
                "description": "Won 1v2 site retake with calm crosshair placement and Phantom spray transfer.",
                "impact": "positive",
                "tilt_indicator": 1
            }
        ]
    }
]
