"""Small translations of the whole window; never deform or resample the art."""
import math


def offset(state, elapsed):
    if state == 'FOUND':
        # Two short hops that settle naturally after a real result.
        return 0, -round(7 * abs(math.sin(elapsed * math.pi * 3)) * max(0, 1-elapsed/1.2))
    if state == 'ANALYZING':
        return round(math.sin(elapsed*3)), -round(2*math.sin(elapsed*2)**2)
    if state == 'RESEARCHING':
        return round(2*math.sin(elapsed*2)), -round(3*math.sin(elapsed*1.8)**2)
    if state == 'WORKING':
        return 0, -round(2*math.sin(elapsed*2.5)**2)
    if state == 'RESPONDING':
        return 0, -round(3*abs(math.sin(elapsed*math.pi))*max(0, 1-elapsed))
    return 0, -round(3*math.sin(elapsed*.9)**2)
