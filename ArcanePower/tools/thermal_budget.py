"""Brayton design-point accounting and environment checks; not a fluid solver."""
import argparse
import json
import math

# Net efficiency ceiling, auxiliary draw, required hot-end temperature Celsius.
# The integrated train/compressor reaches higher tiers as source heat improves.
# Standalone generation is an alternative path for the same heat.
STAGES={'base':(.40,.08,650),'improved':(.55,.07,1000),
        'optimized':(.66,.06,1600),'exotic':(.80,.05,2200)}


def standalone(offered_mw):
    finite(offered_mw,'Offered heat',0)
    return dict(mode='standalone',offered_heat_mw=offered_mw,
                net_mw=offered_mw*.20,rejected_mw=offered_mw*.80,net_efficiency=.20)


def finite(value,name,minimum=None):
    if not math.isfinite(value) or (minimum is not None and value<minimum):
        raise ValueError(name+' is outside its finite physical range')
    return value


def cooling_capacity(kind,rated_mw,density=1,ambient_c=25,sky_view=1,sink_c=-270.15):
    """Ratings are gameplay capacity, normalized for air or radiative conditions."""
    finite(rated_mw,'Cooling rating',0);finite(density,'Relative air density',0)
    finite(ambient_c,'Ambient temperature',-273.15);finite(sink_c,'Radiative sink',-273.15)
    finite(sky_view,'Sky exposure',0)
    if sky_view>1:raise ValueError('Sky exposure must be at most one')
    if kind=='atmosphere':
        # A 20 K approach gives the 45 C reference compressor inlet at 25 C air.
        return rated_mw*min(1,density),max(45,ambient_c+20)
    if kind!='space':raise ValueError('Unknown cooling equipment')
    panel_k=35+273.15;reference_sink_k=3
    factor=max(0,(panel_k**4-(sink_c+273.15)**4)/(panel_k**4-reference_sink_k**4))
    return rated_mw*min(1,factor)*sky_view,45


def budget(offered_mw,stage='base',cooling_mw=None,cold_c=45,hot_c=None,
           flow_capacity_mw=None,duty_trains=4):
    finite(offered_mw,'Offered heat',0);finite(cold_c,'Compressor inlet',-273.15)
    ceiling,aux_ratio,required_hot=STAGES[stage]
    if flow_capacity_mw is not None:finite(flow_capacity_mw,'Flow capacity',0)
    gross_ratio=ceiling+aux_ratio
    hot_c=required_hot if hot_c is None else finite(hot_c,'Turbine inlet',-273.15)
    if hot_c<required_hot:raise ValueError('Primary temperature is too low for this upgrade stage')
    if cooling_mw is not None:finite(cooling_mw,'Available cooling',0)
    hot_k=hot_c+273.15;cold_k=cold_c+273.15
    if hot_k<=0:raise ValueError('Hot reservoir must be above absolute zero')
    reference_carnot=1-(45+273.15)/(required_hot+273.15)
    factor=min(1,max(0,1-cold_k/hot_k)/reference_carnot)
    gross_ratio*=factor
    if type(duty_trains) is not int or not 0<=duty_trains<=4:raise ValueError('Use zero through four independent circuits')
    bank_factor=duty_trains/4
    efficiency=max(0,gross_ratio-aux_ratio)
    gross_ratio=efficiency+aux_ratio
    accepted=offered_mw*bank_factor if efficiency>0 else 0
    if flow_capacity_mw is not None:accepted=min(accepted,flow_capacity_mw)
    gross=accepted*gross_ratio;aux=accepted*aux_ratio
    net=gross-aux;rejected=accepted-net;unaccepted=offered_mw-accepted
    assert math.isclose(offered_mw,net+rejected+unaccepted,rel_tol=1e-12,abs_tol=1e-8)
    assert net>=0 and rejected>=0 and gross_ratio<max(0,1-cold_k/hot_k) or accepted==0
    return dict(stage=stage,offered_heat_mw=offered_mw,accepted_heat_mw=accepted,
                unaccepted_heat_mw=unaccepted,gross_mw=gross,auxiliary_mw=aux,
                net_mw=net,rejected_mw=rejected,net_efficiency=efficiency,
                hot_c=hot_c,cold_c=cold_c,
                available_loop_fraction=bank_factor,
                sustainable_net_mw=net if cooling_mw is None else min(accepted,cooling_mw/(1-efficiency))*efficiency,
                cooling_deficit_mw=0 if cooling_mw is None else max(0,rejected-cooling_mw),
                equipment_efficiency_ceiling=ceiling)



def bank(offered_mw,trains=1,coolers=1,stage='base',
         environment='atmosphere',cooler_rating_mw=60,density=1,ambient_c=25,
         sky_view=1,sink_c=-270.15):
    """100 MWth modules for balance examples; native runtime remains separate."""
    finite(offered_mw,'Offered heat',0)
    counts=dict(trains=trains,coolers=coolers)
    for name,count in counts.items():
        if type(count) is not int or count<0:raise ValueError(name+' must be a non-negative integer')
    if trains>4:raise ValueError('Exactly one turbine per manifold; at most four turbines')
    def point(installed):
        cooling,cold=cooling_capacity(environment,cooler_rating_mw*installed['coolers'],density,ambient_c,sky_view,sink_c)
        duty=min(installed['trains'],installed['coolers']) if offered_mw>0 else 0
        row=budget(offered_mw,stage,cooling,cold,flow_capacity_mw=duty*100,duty_trains=duty)
        limits={'heat supply':offered_mw,'train capacity':duty*100}
        smallest=min(limits.values())
        row.update(duty_trains=duty,standby_trains=0,
                   installed=installed,available_cooling_mw=cooling,
                   bottlenecks=[name for name,limit in limits.items() if math.isclose(limit,smallest,abs_tol=1e-8)],
                   cooling_safe=row['cooling_deficit_mw']<=1e-8)
        return row
    result=point(counts)
    duty=result['duty_trains']
    result['single_circuit_loss_net_mw']=result['net_mw']*(duty-1)/duty if duty else 0
    return result


def check():
    cases=0
    for heat in (0,1,100,25000,250000,2500000):
        for stage in STAGES:
            assert math.isclose(budget(heat,stage)['net_mw'],heat*STAGES[stage][0],rel_tol=1e-12,abs_tol=1e-8)
            cases+=1
    assert math.isclose(standalone(100)['net_mw'],20)
    assert math.isclose(standalone(100)['rejected_mw'],80)
    assert math.isclose(bank(200,2,2)['net_mw'],40)
    assert math.isclose(bank(200,trains=2)['net_mw'],20)
    assert bank(200,trains=2,cooler_rating_mw=20)['cooling_deficit_mw']>0
    resilient=bank(200,4,4)
    assert math.isclose(resilient['single_circuit_loss_net_mw'],60)
    assert bank(100)['single_circuit_loss_net_mw']==0
    for key in ('trains','coolers'):
        assert bank(100,**{key:0})['net_mw']==0
    assert bank(100,environment='atmosphere',density=0)['sustainable_net_mw']==0
    assert bank(100,environment='atmosphere',density=0)['duty_trains']==1
    assert bank(100,environment='atmosphere',density=.2)['cooling_deficit_mw']>0
    assert bank(100,ambient_c=60)['net_mw']<10
    assert math.isclose(bank(100,environment='space')['net_mw'],10)
    assert bank(100,environment='space',sky_view=0)['sustainable_net_mw']==0
    assert bank(100,environment='space',sink_c=35)['sustainable_net_mw']==0
    assert bank(100,environment='space',sink_c=25)['cooling_deficit_mw']>0
    for count in range(1,5):
        assert math.isclose(bank(100,count,count,stage='exotic')['net_mw'],80*count/4)
    assert budget(100,cold_c=650)['accepted_heat_mw']==0
    outputs=[bank(q,2,3)['net_mw'] for q in (99,100,101,110,120,200)]
    assert outputs==sorted(outputs),'Automatic dispatch must not reduce power as more heat becomes available'
    for name in ('trains','coolers'):
        assert bank(200,**{name:3})['net_mw']>=bank(200)['net_mw'],'Adding capacity must not reduce output'
    for value in (-1,float('nan'),float('inf')):
        try:bank(value)
        except ValueError:pass
        else:raise AssertionError('Invalid heat accepted')
    try:budget(100,'exotic',hot_c=650)
    except ValueError:pass
    else:raise AssertionError('Upgrade temperature gate bypassed')
    for count in (-1,1.5,True,5):
        try:bank(100,trains=count)
        except ValueError:pass
        else:raise AssertionError('Invalid module count accepted')
    return {'reference_design_cases':cases,'modular_and_environment_checks':'passed','monotonic_dispatch_and_expansion':'passed',
            'invalid_input_and_temperature_checks':'passed','status':'passed'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--heat-mw',type=float,default=100)
    parser.add_argument('--stage',choices=STAGES,default='base')
    parser.add_argument('--cooler',choices=('space','atmosphere'),default='atmosphere')
    parser.add_argument('--cooling-mw',type=float,default=60)
    parser.add_argument('--density',type=float,default=1)
    parser.add_argument('--ambient-c',type=float,default=25)
    parser.add_argument('--sky-view',type=float,default=1)
    parser.add_argument('--sink-c',type=float,default=-270.15)
    for name in ('trains','coolers'):
        parser.add_argument('--'+name,type=int,default=1)
    args=parser.parse_args()
    print(json.dumps({'self_check':check(),'standalone':standalone(args.heat_mw),
                      'plant':bank(args.heat_mw,args.trains,args.coolers,args.stage,
                                   args.cooler,args.cooling_mw,args.density,args.ambient_c,args.sky_view,args.sink_c),
                      'examples':{'starter':bank(100),'improved':bank(100,stage='improved'),
                                  'premium':bank(100,stage='exotic'),
                                  'four_circuits':bank(200,4,4),'three_circuits':bank(200,3,3)}},indent=2))
