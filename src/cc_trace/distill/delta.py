"""Delta computation between consecutive distillations.

Pure set operations — no LLM calls. Deterministic and fast.
"""

from __future__ import annotations

from cc_trace.distill.models import Delta, Distillation


def compute_delta(current: Distillation, previous: Distillation) -> Delta:
    """Compute the difference between two consecutive distillations.

    Args:
        current: Today's distillation.
        previous: Yesterday's (or previous day's) distillation.

    Returns:
        Delta describing what changed.
    """
    cur_topics = set(current.core_topics)
    prev_topics = set(previous.core_topics)
    cur_interests = set(current.interests)
    prev_interests = set(previous.interests)
    cur_domains = set(current.domain_tags)
    prev_domains = set(previous.domain_tags)

    # New: in current but not in previous (neither topics nor interests)
    prev_all = prev_topics | prev_interests
    new_topics = sorted(cur_topics - prev_all)

    # Faded: in previous but not in current (neither topics nor interests)
    cur_all = cur_topics | cur_interests
    faded_topics = sorted(prev_topics - cur_all)

    # Shifted: moved between core_topics and interests
    shifted = []
    # Was interest, now core topic
    promoted = sorted(cur_topics & prev_interests - prev_topics)
    for t in promoted:
        shifted.append(f"{t}: interest → core")
    # Was core topic, now interest
    demoted = sorted(cur_interests & prev_topics - prev_interests)
    for t in demoted:
        shifted.append(f"{t}: core → interest")

    # Energy level shift
    mood_shift = ""
    if current.energy_level and previous.energy_level:
        if current.energy_level != previous.energy_level:
            mood_shift = f"{previous.energy_level} → {current.energy_level}"

    return Delta(
        current_date=current.date,
        previous_date=previous.date,
        new_topics=new_topics,
        shifted_topics=shifted,
        faded_topics=faded_topics,
        mood_shift=mood_shift,
        new_domains=sorted(cur_domains - prev_domains),
        lost_domains=sorted(prev_domains - cur_domains),
    )
