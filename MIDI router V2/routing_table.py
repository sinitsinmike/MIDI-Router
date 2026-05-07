# =========================================
# file: routing_table.py
# =========================================

# Define the MIDI routing table specifying groups of
#    [MIDI CH, MIDI CMD, source port, destination port]
#
# NB: -1 for CH, CMD or SRC means "any"
# Всего 6 входов и 6 выходов. На корпусе они обозначены 1-6, но в коде они 0-5.

MIDIRT = [
    # In 1 marked on the case, but 0 in the code
    [-1, -1, 0, 0],
    [-1, -1, 0, 1],
    [-1, -1, 0, 2],
    [-1, -1, 0, 3],
    [-1, -1, 0, 4],
    [-1, -1, 0, 5],

    # In 2 marked on the case, but 1 in the code
    [-1, -1, 1, 0],
    [-1, -1, 1, 1],
    [-1, -1, 1, 2],
    [-1, -1, 1, 3],
    [-1, -1, 1, 4],
    [-1, -1, 1, 5],

    # In 3 marked on the case, but 2 in the code
    [-1, -1, 2, 0],
    [-1, -1, 2, 1],
    [-1, -1, 2, 2],
    [-1, -1, 2, 3],
    [-1, -1, 2, 4],
    [-1, -1, 2, 5],

    # In 4 marked on the case, but 3 in the code
    [-1, -1, 3, 0],
    [-1, -1, 3, 1],
    [-1, -1, 3, 2],
    [-1, -1, 3, 3],
    [-1, -1, 3, 4],
    [-1, -1, 3, 5],

    # In 5 marked on the case, but 4 in the code
    [-1, -1, 4, 0],
    [-1, -1, 4, 1],
    [-1, -1, 4, 2],
    [-1, -1, 4, 3],
    [-1, -1, 4, 4],
    [-1, -1, 4, 5],

    # In 6 marked on the case, but 5 in the code
    [-1, -1, 5, 0],
    [-1, -1, 5, 1],
    [-1, -1, 5, 2],
    [-1, -1, 5, 3],
    [-1, -1, 5, 4],
    [-1, -1, 5, 5],
]

# Configure a default route, to be used in the case
# of no other matches.  Set to -1 to disable.
MIDIDEF = -1