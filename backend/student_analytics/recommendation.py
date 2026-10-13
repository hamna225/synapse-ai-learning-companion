def generate_recommendations(analysis):

    recommendations = []

    # Weak topics
    for topic in analysis["weak_topics"]:
        recommendations.append({
            "topic": topic,
            "priority": "high",
            "action": f"Review {topic} and practice basic questions."
        })

    # Practice topics
    for topic in analysis["practice_topics"]:
        recommendations.append({
            "topic": topic,
            "priority": "medium",
            "action": f"Practice more questions on {topic}."
        })

    # Strong topics
    for topic in analysis["strong_topics"]:
        recommendations.append({
            "topic": topic,
            "priority": "low",
            "action": f"Try advanced questions on {topic}."
        })

    return recommendations