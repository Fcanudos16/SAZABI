import math
from ui.presentation import SazabiPresentationController, transform_pixels, transform_point


def test_transform_preserves_original_data_and_palette():
    rgb = bytes((20, 30, 40))*400
    mask = bytes(1 if 5 <= x < 15 and 5 <= y < 15 else 0 for y in range(20) for x in range(20))
    original = rgb, mask
    for angle in range(-3, 4):
        output, shape = transform_pixels(rgb, mask, 20, 20, angle, .98)
        assert sum(shape) > 80
        assert all(output[i*3:i*3+3] == bytes((20, 30, 40)) for i, on in enumerate(shape) if on)
    assert (rgb, mask) == original
    assert transform_pixels(rgb, mask, 20, 20, 0, 1) == original


def test_presentation_animates_each_pose_with_bounded_whole_body_transforms():
    for state in ('IDLE', 'WORKING', 'DRAGGING', 'LANDING', 'SLEEPING', 'WAKE_UP', 'CONFIGURATION', 'EXIT_HOVER', 'FOUND', 'RESPONDING'):
        controller = SazabiPresentationController()
        samples = []
        for i in range(160):
            t = i*.05
            controller.drag(math.sin(t)*8)
            samples.append(controller.sample(t, state, depth=min(1, t), work_x=3*math.sin(t),
                                              landing_scale=.99+.01*math.cos(t), state_elapsed=t))
        assert len(set(samples)) > 1, state
        assert all(-3 <= angle <= 3 and .98 <= scale <= 1 for angle, scale in samples)
    controller.reset()
    assert (controller.angle, controller.scale, controller.drag_impulse) == (0, 1, 0)


def test_presentation_eyelids_and_art_share_the_same_transform():
    # A source marker must appear within one pixel of its composited location.
    width, height = 30, 40
    rgb, mask = bytearray(width*height*3), bytearray(width*height)
    for y in range(15, 20):
        for x in range(12, 17):
            mask[y*width+x] = 1
    _, shape = transform_pixels(rgb, mask, width, height, 3, .99)
    x, y = transform_point(14, 17, width, height, 3, .99)
    assert shape[round(y)*width+round(x)]
