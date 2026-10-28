"""Compare plant output, fuel use and effective cooling at the gameplay balance."""
import argparse
import json
import math

FUEL_GW = {'aether': 5, 'helion': 50, 'empyrean': 250}
TURBINE_GW = {1: 3.5, 2: 50}


def budget(fuel='aether', mode='brayton', turbine_tier=1, circuits=4,
           load=1, cooling_gw=None):
    """Cooling capacity is effective GW per circuit, after environment losses."""
    if fuel not in FUEL_GW or mode not in ('standalone', 'brayton'):
        raise ValueError('Unknown fuel or mode')
    if type(turbine_tier) is not int or turbine_tier not in TURBINE_GW:
        raise ValueError('Use turbine tier 1 or 2')
    if type(circuits) is not int or not 0 <= circuits <= 4:
        raise ValueError('Use zero through four independent circuits')
    if not math.isfinite(load) or not 0 <= load <= 1:
        raise ValueError('Load must be finite and between zero and one')
    if cooling_gw is not None and (not math.isfinite(cooling_gw) or cooling_gw < 0):
        raise ValueError('Effective cooling must be finite and nonnegative')
    if mode == 'standalone' and fuel != 'aether':
        raise ValueError('Standalone operation requires Aether')
    if mode == 'brayton' and fuel == 'empyrean' and turbine_tier != 2:
        raise ValueError('Empyrean requires upgraded turbines')
    rating = FUEL_GW[fuel]
    efficiency = .1 if mode == 'standalone' else .8
    maximum = rating * efficiency if mode == 'standalone' else min(
        rating * efficiency / 4, TURBINE_GW[turbine_tier]) * circuits
    output = maximum * load
    fuel_input = output / efficiency
    cooling = fuel_input - output if mode == 'standalone' else output
    per_circuit = cooling / circuits if mode == 'brayton' and circuits else 0
    margin = None if cooling_gw is None or mode == 'standalone' else cooling_gw - per_circuit
    return dict(fuel=fuel, mode=mode, fuel_rating_gw=rating, conversion=efficiency,
                maximum_output_gw=maximum, output_gw=output, fuel_input_gw=fuel_input,
                fuel_utilization=fuel_input / rating,
                cooling_load_gw=cooling, cooling_per_circuit_gw=per_circuit,
                cooling_margin_per_circuit_gw=margin,
                cooling_safe=margin is None or margin >= -1e-12,
                cooling_integrated=mode == 'standalone')


def check():
    ladder = [('aether', 'standalone', 1, .5), ('aether', 'brayton', 1, 4),
              ('helion', 'brayton', 1, 14), ('helion', 'brayton', 2, 40),
              ('empyrean', 'brayton', 2, 200)]
    for fuel, mode, tier, output in ladder:
        for circuits in range(5):
            for load in (0, .25, .5, 1):
                point = budget(fuel, mode, tier, circuits, load)
                expected = output * load * (1 if mode == 'standalone' else circuits / 4)
                assert math.isclose(point['output_gw'], expected, abs_tol=1e-12)
                assert point['fuel_utilization'] <= 1
                if mode == 'brayton':
                    assert point['cooling_load_gw'] == point['output_gw']
    assert budget('helion', cooling_gw=3.5)['cooling_safe']
    assert not budget('helion', cooling_gw=3)['cooling_safe']
    assert budget('empyrean', turbine_tier=2, cooling_gw=50)['cooling_safe']
    assert not budget('empyrean', turbine_tier=2, cooling_gw=49)['cooling_safe']
    for args in ({'fuel': 'empyrean'}, {'circuits': 5}, {'load': float('nan')},
                 {'load': -1}, {'cooling_gw': -1}, {'mode': 'standalone', 'fuel': 'helion'}):
        try:
            budget(**args)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid plant accepted: ' + str(args))
    return 'passed'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fuel', choices=FUEL_GW, default='aether')
    parser.add_argument('--mode', choices=('standalone', 'brayton'), default='brayton')
    parser.add_argument('--turbine-tier', type=int, choices=TURBINE_GW, default=1)
    parser.add_argument('--circuits', type=int, default=4)
    parser.add_argument('--load', type=float, default=1)
    parser.add_argument('--cooling-gw', type=float, help='Effective cooling GW per circuit')
    args = parser.parse_args()
    print(json.dumps({'self_check': check(), 'plant': budget(**vars(args))}, indent=2))
