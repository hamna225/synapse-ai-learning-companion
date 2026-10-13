"""Run deterministic synthetic learners through the production BKT updater."""

import json
import random
from pathlib import Path

from student_analytics.learner_profile import update_bkt


PROFILES = {
    "balanced": {"Foundations": 0.55, "Supervised": 0.50, "Reinforcement": 0.45},
    "advanced": {"Foundations": 0.85, "Supervised": 0.72, "Reinforcement": 0.62},
    "needs_foundations": {"Foundations": 0.38, "Supervised": 0.32, "Reinforcement": 0.25},
}
SESSIONS = 5
QUESTIONS_PER_SESSION = 5
SEED = 2026
REPLICATES = 100


def simulate():
    rng = random.Random(SEED)
    results = []

    for name, initial_skill in PROFILES.items():
        gains = []
        accuracies = []
        final_mastery = {topic: [] for topic in initial_skill}
        topic_session_counts = {topic: 0 for topic in initial_skill}

        for _replicate in range(REPLICATES):
            skill = dict(initial_skill)
            mastery = {topic: 0.2 for topic in skill}
            first_estimates = dict(mastery)
            correct_answers = 0
            total_answers = 0

            for _session in range(SESSIONS):
                topic = min(mastery, key=mastery.get)
                topic_session_counts[topic] += 1

                for _ in range(QUESTIONS_PER_SESSION):
                    correct = rng.random() < skill[topic]
                    correct_answers += int(correct)
                    total_answers += 1
                    mastery[topic] = update_bkt(mastery[topic], correct)

                # Synthetic assumption: focused practice raises the learner's
                # response probability by four points, capped at 95%.
                skill[topic] = min(0.95, skill[topic] + 0.04)

            for topic in mastery:
                final_mastery[topic].append(mastery[topic])
            gains.append(
                sum(mastery[t] - first_estimates[t] for t in mastery)
                / len(mastery) * 100
            )
            accuracies.append(correct_answers / total_answers * 100)

        results.append({
            "profile": name,
            "replicates": REPLICATES,
            "sessions_per_replicate": SESSIONS,
            "questions_per_replicate": SESSIONS * QUESTIONS_PER_SESSION,
            "topic_session_selections_across_replicates": topic_session_counts,
            "mastery_end_percent": {
                topic: round(sum(values) / len(values) * 100, 1)
                for topic, values in final_mastery.items()
            },
            "mean_estimated_mastery_gain_points": round(sum(gains) / len(gains), 1),
            "simulated_accuracy_percent": round(sum(accuracies) / len(accuracies), 1),
        })

    return {
        "method": "Monte Carlo synthetic responses updated with the production BKT function; weakest estimated topic is selected each session.",
        "seed": SEED,
        "replicates_per_profile": REPLICATES,
        "sessions_per_profile": SESSIONS,
        "questions_per_session": QUESTIONS_PER_SESSION,
        "assumption": "After each focused practice session, that topic's synthetic response probability increases by 4 percentage points, capped at 95%.",
        "results": results,
        "question_repetition_rate": "Not measured by this learner-model simulation; it does not call the live question generator.",
    }


if __name__ == "__main__":
    result = simulate()
    output = Path(__file__).with_name("learner_simulation_results.json")
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"Results saved to {output}")
