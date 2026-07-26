"""Parser/validator: table-driven bad screenplays -> expected error codes,
plus a known-good screenplay that must check clean."""
from __future__ import annotations

import pytest

from conftest import compile_production, error_codes

# a minimal valid wrapper the bad snippets build on
HEAD = """
motionforge: 1
meta: {resolution: [192, 108], fps: 12, seed: 0}
characters:
  asha: {body: human, height: 1.6}
"""

BAD_CASES = [
    # (test id, screenplay, expected code)
    ("missing_version", """
        meta: {fps: 12}
        scenes:
          - id: s
            duration: 2.0
        """, "E104"),
    ("bad_version", """
        motionforge: 3
        scenes:
          - id: s
            duration: 2.0
        """, "E105"),
    ("no_scenes", """
        motionforge: 1
        meta: {fps: 12}
        """, "E106"),
    ("duplicate_scene_id", HEAD + """
        scenes:
          - {id: s, duration: 2.0}
          - {id: s, duration: 2.0}
        """, "E107"),
    ("unknown_top_key", HEAD + """
        scenies: []
        scenes:
          - {id: s, duration: 2.0}
        """, "E110"),
    ("fps_not_a_number", """
        motionforge: 1
        meta: {fps: fast}
        scenes:
          - {id: s, duration: 2.0}
        """, "E112"),
    ("bad_resolution", """
        motionforge: 1
        meta: {resolution: [192, 108, 3]}
        scenes:
          - {id: s, duration: 2.0}
        """, "E115"),
    ("bad_at_vector", HEAD + """
        scenes:
          - id: s
            duration: 2.0
            place:
              - {char: asha, at: [1, 2, 3]}
        """, "E115"),
    ("unknown_depth", HEAD + """
        scenes:
          - id: s
            duration: 2.0
            place:
              - {char: asha, at: [0, 0], depth: nearr}
        """, "E118"),
    ("place_without_subject", HEAD + """
        scenes:
          - id: s
            duration: 2.0
            place:
              - {at: [0, 0]}
        """, "E120"),
    ("place_char_and_obj", HEAD + """
        scenes:
          - id: s
            duration: 2.0
            place:
              - {char: asha, obj: tree, at: [0, 0]}
        """, "E120"),
    ("direction_without_verb", HEAD + """
        scenes:
          - id: s
            duration: 2.0
            place:
              - {char: asha, at: [0, 0]}
            timeline:
              - {t: 0.5, char: asha}
        """, "E125"),
    ("camera_keys_and_follow", HEAD + """
        scenes:
          - id: s
            duration: 2.0
            camera:
              keys:
                - {t: 0, x: 0, zoom: 1.0}
              follow: {char: asha}
            place:
              - {char: asha, at: [0, 0]}
        """, "E127"),
    ("unknown_character_placed", HEAD + """
        scenes:
          - id: s
            duration: 2.0
            place:
              - {char: ahsa, at: [0, 0]}
        """, "E200"),
    ("duplicate_placement_id", HEAD + """
        scenes:
          - id: s
            duration: 2.0
            place:
              - {char: asha, at: [0, 0]}
              - {char: asha, at: [2, 0]}
        """, "E201"),
    ("timeline_unknown_char", HEAD + """
        scenes:
          - id: s
            duration: 4.0
            place:
              - {char: asha, at: [0, 0]}
            timeline:
              - {t: 0.5, char: ahsa, do: walk, to: [2, 0], until: 3.0}
        """, "E202"),
    ("char_direction_on_object", HEAD + """
        scenes:
          - id: s
            duration: 4.0
            place:
              - {obj: tree, id: oak, at: [1, 0]}
            timeline:
              - {t: 0.5, char: oak, do: wave}
        """, "E203"),
    ("unknown_verb", HEAD + """
        scenes:
          - id: s
            duration: 4.0
            place:
              - {char: asha, at: [0, 0]}
            timeline:
              - {t: 0.5, char: asha, do: frolic}
        """, "E220"),
    ("walk_without_destination", HEAD + """
        scenes:
          - id: s
            duration: 4.0
            place:
              - {char: asha, at: [0, 0]}
            timeline:
              - {t: 0.5, char: asha, do: walk, until: 3.0}
        """, "E221"),
    ("pickup_unknown_object", HEAD + """
        scenes:
          - id: s
            duration: 4.0
            place:
              - {char: asha, at: [0, 0]}
            timeline:
              - {t: 0.5, char: asha, do: pickup, obj: basket}
        """, "E223"),
    ("until_before_t", HEAD + """
        scenes:
          - id: s
            duration: 4.0
            place:
              - {char: asha, at: [0, 0]}
            timeline:
              - {t: 2.0, char: asha, do: walk, to: [2, 0], until: 1.0}
        """, "E300"),
    ("starts_after_scene_end", HEAD + """
        scenes:
          - id: s
            duration: 2.0
            place:
              - {char: asha, at: [0, 0]}
            timeline:
              - {t: 3.0, char: asha, do: wave}
        """, "E301"),
    ("overlapping_locomotion", HEAD + """
        scenes:
          - id: s
            duration: 6.0
            place:
              - {char: asha, at: [0, 0]}
            timeline:
              - {t: 0.5, char: asha, do: walk, to: [3, 0], until: 4.0}
              - {t: 2.0, char: asha, do: walk, to: [0, 0], until: 5.5}
        """, "E310"),
    ("catch_without_throw", HEAD + """
        scenes:
          - id: s
            duration: 4.0
            place:
              - {char: asha, at: [0, 0]}
              - {obj: ball, at: [1, 0]}
            timeline:
              - {t: 1.0, char: asha, do: catch, obj: ball}
        """, "E340"),
    ("unknown_sfx", HEAD + """
        scenes:
          - id: s
            duration: 2.0
            timeline:
              - {t: 0.5, sfx: kaboom}
        """, "E501"),
    ("unknown_expression", HEAD + """
        scenes:
          - id: s
            duration: 4.0
            place:
              - {char: asha, at: [0, 0]}
            timeline:
              - {t: 0.5, char: asha, emote: bamboozled}
        """, "E502"),
    ("unknown_music_mood", HEAD + """
        scenes:
          - {id: s, duration: 2.0}
        audio:
          music: {mood: dubstep}
        """, "E503"),
]


@pytest.mark.parametrize("name,screenplay,code",
                         BAD_CASES, ids=[c[0] for c in BAD_CASES])
def test_bad_screenplay_reports_code(name, screenplay, code):
    codes = error_codes(screenplay)
    assert code in codes, f"expected {code} for '{name}', got {sorted(codes)}"


GOOD = """
motionforge: 1
meta:
  title: "Good"
  resolution: [192, 108]
  fps: 12
  seed: 7
palette:
  brick: "#b5502a"
characters:
  asha: {body: human, height: 1.6, skin: "#c68642"}
scenes:
  - id: dawn
    duration: 6.0
    background: {sky: dawn, ground: {kind: grass}}
    transition_in: {type: fade, dur: 0.5}
    camera:
      keys:
        - {t: 0, x: 0, y: 1.2, zoom: 1.0}
        - {t: 5, x: 2, zoom: 1.2, ease: in_out}
    place:
      - {char: asha, at: [-2, 0], depth: near, facing: right}
      - {obj: windmill, id: mill, at: [6, 0], depth: far, scale: 1.2, tint: brick}
    timeline:
      - {t: 0.5, char: asha, do: walk, to: [1, 0], until: 4.0}
      - {t: 1.0, obj: mill, part: blades, spin: {rpm: 6}}
      - {t: 4.2, char: asha, do: wave, until: 5.5}
      - {t: 4.0, sfx: birdsong}
    captions:
      - {t: 0.0, until: 2.0, text: "Chapter One", style: title}
audio:
  music: {mood: pastoral, volume: 0.6}
"""


def test_good_screenplay_is_clean():
    prod, report = compile_production(GOOD)
    assert prod is not None
    assert report.ok, report.format()
    assert report.items == [], "clean screenplay should have no findings: " \
        + report.format()


def test_error_messages_carry_suggestions():
    _prod, report = compile_production(HEAD + """
        scenes:
          - id: s
            duration: 4.0
            place:
              - {char: asha, at: [0, 0]}
            timeline:
              - {t: 0.5, char: ahsa, do: wave}
        """)
    errs = [e for e in report.items if e.code == "E202"]
    assert errs, report.format()
    assert "asha" in errs[0].suggestion  # did-you-mean fires
