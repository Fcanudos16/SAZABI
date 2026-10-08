import hashlib
import json

from ui.sprites import foreground_mask, region_data, ASSETS
from ui.native import place_near


def test_original_art_and_six_explicit_viewports():
    config = json.loads((ASSETS / 'states.json').read_text())
    assert hashlib.sha256((ASSETS / config['image']).read_bytes()).hexdigest() == config['sha256']
    assert set(config['states']) == {'IDLE', 'WORKING', 'FOUND', 'LANDING', 'CONFIGURATION', 'EXIT_HOVER'}
    assert len({tuple(rect) for rect in config['states'].values()}) == 6
    assert config['states']['IDLE'] == [215, 65, 355, 285]
    assert config['state_models']['RESPONDING'] != 'EXIT_HOVER'
    assert config['state_models']['DRAGGING'] == config['state_models']['WORKING']


def test_background_region_preserves_enclosed_white_eyes_and_rgb():
    pixels = bytearray(b'\xff' * 7*7*3)
    for y in range(1, 6):
        for x in range(1, 6):
            if x in (1, 5) or y in (1, 5):
                i = (y*7+x)*3
                pixels[i:i+3] = b'\x12\x12\x12'
    before = bytes(pixels)
    mask = foreground_mask(pixels, 7, 7)
    assert not mask[0] and mask[3*7+3] and mask[1*7+1]
    assert bytes(pixels) == before, 'Masking must not edit the artwork'
    assert len(region_data(mask, 7, 7)) > 32


def test_terminal_position_stays_in_each_monitor_work_area():
    for area in ((0, 0, 1920, 1040), (-1280, 0, 0, 984), (0, -1080, 1920, 0)):
        for x, y in ((area[0], area[1]), (area[2]-190, area[3]-220)):
            px, py = place_near(x, y, 190, 220, 620, 440, area)
            assert area[0] <= px and px+620 <= area[2]
            assert area[1] <= py and py+440 <= area[3]


def test_mask_removes_white_matted_colored_fringe_without_editing_rgb():
    pixels = bytearray(bytes((130, 180, 190)) * 49)
    for y in range(2, 5):
        for x in range(2, 5):
            i = (y*7+x)*3
            pixels[i:i+3] = bytes((18, 30, 40))
    pixels[72:75] = bytes((255, 255, 255))
    original = bytes(pixels)
    mask = foreground_mask(pixels, 7, 7)
    assert not mask[8] and mask[16] and mask[24]
    assert bytes(pixels) == original


def test_motion_stays_bounded_and_celebration_settles():
    from ui.motion import offset
    for state in ('IDLE', 'ANALYZING', 'RESEARCHING', 'WORKING', 'FOUND', 'RESPONDING'):
        samples = [offset(state, i/20) for i in range(101)]
        assert len(set(samples)) > 1
        assert all(abs(x) <= 2 and -7 <= y <= 0 for x, y in samples)
    assert offset('FOUND', 1.3) == offset('RESPONDING', 1.3) == (0, 0)


def test_real_pipeline_events_have_no_fabricated_success(agent):
    events = []
    agent.event_sink = lambda kind, data: events.append((kind, data))
    agent.handle('/search clínicas em Campinas')
    kinds = [kind for kind, _ in events]
    assert kinds[0] == 'SEARCH_STARTED'
    assert 'SEARCH_PROCESSING' in kinds and 'SEARCH_RESULT_FOUND' in kinds
    assert kinds[-1] == 'SEARCH_COMPLETED'
    assert events[-1][1]['companies'] == agent.runs.last().new_count
    events.clear()
    agent.finder.sources = []
    agent.handle('/search clínicas em Campinas')
    assert [kind for kind, _ in events] == ['TASK_ERROR']


def test_no_results_never_emits_found(agent):
    events = []
    agent.event_sink = lambda kind, data: events.append((kind, data))
    agent.handle('/search segmento inexistente em Cidade Inexistente')
    assert 'SEARCH_RESULT_FOUND' not in [kind for kind, _ in events]
    assert events[-1][0] == 'SEARCH_COMPLETED'
    assert events[-1][1]['companies'] == events[-1][1]['pages'] == 0
