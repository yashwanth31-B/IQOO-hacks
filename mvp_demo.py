#!/usr/bin/env python3
"""
MVP USER FLOW & DATA MODEL DEMONSTRATION
Gaming Second Brain - AI Gaming Copilot Intelligence & Memory Layer

Demonstrates:
- Full 10-Step User Flow from Session Completion to AI Recommendations
- Robust Data Model with optional fields
"""

import os
import sys
import json

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models import Session
from app.mvp_flow import (
    record_mvp_session,
    search_and_analyze_best_performance,
    compare_session_with_history,
    generate_personalized_recommendation,
    generate_ai_memory_summary
)

def print_separator(title=""):
    print("\n" + "=" * 70)
    if title:
        print(f" {title.upper()} ")
        print("=" * 70)

def run_mvp_flow_demo():
    print_separator("Gaming Second Brain — 10-Step MVP User Flow")
    
    # -------------------------------------------------------------
    # STEP 1: User completes a gaming session.
    # -------------------------------------------------------------
    print("\n[STEP 1] User completes a gaming session.")
    print("Player finishes a 72-minute ranked match on Ascent in Valorant.")

    # -------------------------------------------------------------
    # STEP 2: The system records session information.
    # -------------------------------------------------------------
    print_separator("STEP 2: The system records session information")
    session_data = {
        "session_id": "18",
        "game": "Valorant",
        "date": "2026-09-17T20:00:00",
        "duration": "72 minutes",
        "score": "18/10",
        "kills": 18,
        "deaths": 10,
        "assists": 6,
        "result": "Win",
        "map": "Ascent",
        "configuration": "Phantom + preferred sensitivity",
        "performance_metrics": {
            "kd": 1.8,
            "acs": 285,
            "headshot_pct": 32,
            "first_bloods": 5
        },
        "player_notes": "Felt locked in. Sensitivity tweak was perfect, crosshair didn't jitter once."
    }

    # Verify Data Model
    session_obj = Session(**session_data)
    print("Session Object recorded:")
    print(f"  Session #{session_obj.session_id}")
    print(f"  Game: {session_obj.game}")
    print(f"  Duration: {session_obj.duration}")
    print(f"  Score: {session_obj.score}")
    print(f"  K/D: {session_obj.performance_metrics.get('kd')}")
    print(f"  Configuration: {session_obj.configuration}")
    print(f"  Map: {session_obj.map}")
    print(f"  Result: {session_obj.result}")

    # -------------------------------------------------------------
    # STEP 3: AI creates a short memory summary.
    # -------------------------------------------------------------
    print_separator("STEP 3: AI creates a short memory summary")
    ai_summary = generate_ai_memory_summary(session_data)
    print(f'AI Summary: "{ai_summary}"')

    # -------------------------------------------------------------
    # STEP 4: Store the structured session and AI-generated memory.
    # -------------------------------------------------------------
    print_separator("STEP 4: Store structured session & AI memory")
    result = record_mvp_session(session_obj)
    print(f"Stored structured Session #{result['session_id']} (DB ID: {result['db_id']})")
    print(f"Created Episodic Memory Node #{result['memory_id']}")
    print(f"AI Insights: {result['ai_insights']}")

    # -------------------------------------------------------------
    # STEP 5: User asks a natural-language question.
    # -------------------------------------------------------------
    print_separator("STEP 5: User asks a natural-language question")
    user_q1 = "When did I perform best?"
    print(f'User Query: "{user_q1}"')

    # -------------------------------------------------------------
    # STEP 6: The system searches previous sessions.
    # STEP 7: AI analyzes the retrieved sessions.
    # STEP 8: Return an explanation with evidence from stored sessions.
    # -------------------------------------------------------------
    print_separator("STEPS 6 - 8: Search, Analyze & Return Evidence")
    step6_8 = search_and_analyze_best_performance(user_q1)
    print(f"System searched previous sessions ({step6_8['evidence'].get('total_sessions_analyzed')} sessions evaluated).")
    print("AI analyzed K/D ratios, match outcomes, and configurations.")
    print("\nAI Explanation with Evidence:")
    print(step6_8["explanation"])

    # -------------------------------------------------------------
    # STEP 9: User asks: "What was different?"
    # AI compares Session #18 with relevant previous sessions.
    # -------------------------------------------------------------
    print_separator("STEP 9: User asks: 'What was different?'")
    user_q2 = "What was different?"
    print(f'User Query: "{user_q2}"')
    step9 = compare_session_with_history(target_session_id="18", query=user_q2)
    print("\nAI Comparative Analysis:")
    print(step9["explanation"])

    # -------------------------------------------------------------
    # STEP 10: User asks: "What should I do next?"
    # AI generates a personalized recommendation based on historical data.
    # -------------------------------------------------------------
    print_separator("STEP 10: User asks: 'What should I do next?'")
    user_q3 = "What should I do next?"
    print(f'User Query: "{user_q3}"')
    step10 = generate_personalized_recommendation(target_session_id="18", query=user_q3)
    print("\nAI Personalized Recommendations:")
    print(step10["explanation"])

    # -------------------------------------------------------------
    # DATA MODEL ROBUSTNESS DEMO (Missing fields test)
    # -------------------------------------------------------------
    print_separator("Data Model Robustness Demo (Missing Fields)")
    sparse_session = Session(
        game="Valorant",
        score="15/12",
        result="Win"
    )
    print("Session created with only 3 fields (all other 12 fields omitted/defaulted):")
    print(sparse_session.model_dump(exclude_none=True))
    sparse_summary = generate_ai_memory_summary(sparse_session.model_dump())
    print(f'Generated AI Summary for sparse session: "{sparse_summary}"')

    print_separator("All 10 MVP Steps & Data Model Verified Successfully!")

if __name__ == "__main__":
    run_mvp_flow_demo()
