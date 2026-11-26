"""Which tour a user should see.

TOUR_VERSION goes up when steps are added. Steps added in a version carry
"v": <that version> in templates/partials/_tour.html.

    never finished the tour        -> 'full'   (every step)
    finished an older version      -> 'new'    (only the steps added since)
    current version, or replayed   -> None     (nothing starts by itself)

A NULL users.tour_version counts as version 1, which is what everyone who
finished the tour before versions existed has.
"""

TOUR_VERSION = 2


def tour_mode(user):
    if user is None:
        return None
    if user.tour_completed_at is None:
        return 'full'
    if (user.tour_version or 1) < TOUR_VERSION:
        return 'new'
    return None
