"""Priority, never conversion probability. Repeated signals do not add points."""
WEIGHTS = {'growth': 20, 'new_unit': 20, 'multiple_locations': 15,
           'manual_process': 20, 'hiring': 10, 'scheduling': 15,
           'customer_service': 10, 'operational_complexity': 10, 'ecommerce': 10}


def opportunity_score(signals):
    verified = [s for s in signals if s.source_url and s.evidence and s.source]
    types = {s.type for s in verified}
    score = sum(WEIGHTS.get(kind, 0) for kind in types)
    if any(s.confidence == 'high' for s in verified):
        score += 10
    return min(100, score)
