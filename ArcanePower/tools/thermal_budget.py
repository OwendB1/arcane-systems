"""Brayton design-point accounting and environment checks; not a fluid solver."""
import argparse
import json
import math

# Net efficiency ceiling, auxiliary draw, required hot-end temperature Celsius.
# One recovery unit per duty train starts at 40%; sufficient exotic recovery
# reaches 78%. Standalone generation is an alternative path for the same heat.
STAGES={'base':(.55,.08,650),'recuperated':(.66,.07,1000),
        'optimized':(.74,.06,1600),'exotic':(.78,.05,2200)}


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
           recovery_ratio=1,flow_capacity_mw=None):
    finite(offered_mw,'Offered heat',0);finite(cold_c,'Compressor inlet',-273.15)
    ceiling,aux_ratio,required_hot=STAGES[stage]
    finite(recovery_ratio,'Recovery capacity ratio',0)
    if flow_capacity_mw is not None:finite(flow_capacity_mw,'Flow capacity',0)
    recovered=min(.78,.40+.40*(1-2**(-max(0,recovery_ratio-1))))
    gross_ratio=min(ceiling,recovered)+aux_ratio
    hot_c=required_hot if hot_c is None else finite(hot_c,'Turbine inlet',-273.15)
    if hot_c<required_hot:raise ValueError('Primary temperature is too low for this upgrade stage')
    if cooling_mw is not None:finite(cooling_mw,'Available cooling',0)
    hot_k=hot_c+273.15;cold_k=cold_c+273.15
    if hot_k<=0:raise ValueError('Hot reservoir must be above absolute zero')
    reference_carnot=1-(45+273.15)/(required_hot+273.15)
    factor=min(1,max(0,1-cold_k/hot_k)/reference_carnot)
    gross_ratio*=factor
    efficiency=max(0,gross_ratio-aux_ratio)
    accepted=offered_mw if efficiency>0 and recovery_ratio>0 else 0
    if flow_capacity_mw is not None:accepted=min(accepted,flow_capacity_mw)
    if cooling_mw is not None:accepted=min(accepted,cooling_mw/(1-efficiency))
    gross=accepted*gross_ratio;aux=accepted*aux_ratio
    net=gross-aux;rejected=accepted-net;unaccepted=offered_mw-accepted
    assert math.isclose(offered_mw,net+rejected+unaccepted,rel_tol=1e-12,abs_tol=1e-8)
    assert net>=0 and rejected>=0 and gross_ratio<max(0,1-cold_k/hot_k) or accepted==0
    return dict(stage=stage,offered_heat_mw=offered_mw,accepted_heat_mw=accepted,
                unaccepted_heat_mw=unaccepted,gross_mw=gross,auxiliary_mw=aux,
                net_mw=net,rejected_mw=rejected,net_efficiency=efficiency,
                hot_c=hot_c,cold_c=cold_c,recovery_ratio=recovery_ratio,
                equipment_efficiency_ceiling=ceiling)



def bank(offered_mw,heaters=1,trains=1,recuperators=1,coolers=1,stage='base',
         environment='atmosphere',cooler_rating_mw=60,density=1,ambient_c=25,
         sky_view=1,sink_c=-270.15):
    """100 MWth modules for balance examples; native runtime remains separate."""
    finite(offered_mw,'Offered heat',0)
    counts=dict(heaters=heaters,trains=trains,recuperators=recuperators,coolers=coolers)
    for name,count in counts.items():
        if type(count) is not int or count<0:raise ValueError(name+' must be a non-negative integer')
    def point(installed):
        cooling,cold=cooling_capacity(environment,cooler_rating_mw*installed['coolers'],density,ambient_c,sky_view,sink_c)
        maximum=min(math.ceil(offered_mw/100),installed['heaters'],installed['trains'],installed['recuperators'])
        candidates=[]
        for duty in range(maximum+1):
            design_flow=duty*100
            ratio=installed['recuperators']*100/design_flow if design_flow else 0
            row=budget(offered_mw,stage,cooling,cold,recovery_ratio=ratio,
                       flow_capacity_mw=min(design_flow,installed['recuperators']*100))
            candidates.append((row['net_mw'],-duty,row))
        _,negative_duty,row=max(candidates,key=lambda item:(item[0],item[1]))
        duty=-negative_duty
        limits={'heat supply':offered_mw,'heater capacity':installed['heaters']*100,
                'train capacity':installed['trains']*100,'dispatched bank':duty*100,'recovery capacity':installed['recuperators']*100,
                'cooling capacity':cooling/(1-row['net_efficiency'])}
        smallest=min(limits.values())
        row.update(duty_trains=duty,standby_trains=installed['trains']-duty,
                   duty_heaters=duty,standby_heaters=installed['heaters']-duty,
                   installed=installed,available_cooling_mw=cooling,
                   bottlenecks=[name for name,limit in limits.items() if math.isclose(limit,smallest,abs_tol=1e-8)])
        return row
    result=point(counts)
    losses={name:point(dict(counts,**{name:count-1}))['net_mw'] for name,count in counts.items() if count}
    result['single_module_loss_net_mw']=losses
    result['guaranteed_single_module_loss_net_mw']=min([result['net_mw']]+list(losses.values()))
    return result


def check():
    cases=0
    for heat in (0,1,100,25000,250000,2500000):
        for stage in STAGES:
            assert math.isclose(budget(heat,stage)['net_mw'],heat*.4,rel_tol=1e-12,abs_tol=1e-8)
            cases+=1
    assert math.isclose(bank(100,recuperators=2)['net_mw'],55)
    assert math.isclose(bank(100,recuperators=6,stage='exotic')['net_mw'],78)
    assert math.isclose(bank(100,recuperators=100,stage='exotic')['net_mw'],78)
    assert math.isclose(standalone(100)['net_mw'],20)
    assert math.isclose(standalone(100)['rejected_mw'],80)
    assert math.isclose(bank(100,recuperators=6)['net_mw'],55)
    assert math.isclose(bank(200,2,2,2,2)['net_mw'],80)
    assert math.isclose(bank(200,trains=2)['net_mw'],40)  # one heater is still the bottleneck
    resilient=bank(200,3,3,3,3)
    assert resilient['standby_trains']==1
    assert math.isclose(resilient['guaranteed_single_module_loss_net_mw'],80)
    assert bank(100)['guaranteed_single_module_loss_net_mw']==0
    for key in ('heaters','trains','recuperators','coolers'):
        assert bank(100,**{key:0})['net_mw']==0
    assert bank(100,environment='atmosphere',density=0)['net_mw']==0
    assert bank(100,environment='atmosphere',density=0)['duty_trains']==0
    assert bank(100,environment='atmosphere',density=.2)['net_mw']<40
    assert bank(100,ambient_c=60)['net_mw']<40
    assert math.isclose(bank(100,environment='space')['net_mw'],40)
    assert bank(100,environment='space',sky_view=0)['net_mw']==0
    assert bank(100,environment='space',sink_c=35)['net_mw']==0
    assert 0<bank(100,environment='space',sink_c=25)['net_mw']<40
    assert budget(100,cold_c=650)['accepted_heat_mw']==0
    outputs=[bank(q,2,2,3,3)['net_mw'] for q in (99,100,101,110,120,200)]
    assert outputs==sorted(outputs),'Automatic dispatch must not reduce power as more heat becomes available'
    for name in ('heaters','trains','recuperators','coolers'):
        assert bank(200,**{name:3})['net_mw']>=bank(200)['net_mw'],'Adding capacity must not reduce output'
    for value in (-1,float('nan'),float('inf')):
        try:bank(value)
        except ValueError:pass
        else:raise AssertionError('Invalid heat accepted')
    try:budget(100,'exotic',hot_c=650)
    except ValueError:pass
    else:raise AssertionError('Upgrade temperature gate bypassed')
    for count in (-1,1.5,True):
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
    for name in ('heaters','trains','recuperators','coolers'):
        parser.add_argument('--'+name,type=int,default=1)
    args=parser.parse_args()
    print(json.dumps({'self_check':check(),'standalone':standalone(args.heat_mw),
                      'plant':bank(args.heat_mw,args.heaters,args.trains,args.recuperators,args.coolers,args.stage,
                                   args.cooler,args.cooling_mw,args.density,args.ambient_c,args.sky_view,args.sink_c),
                      'examples':{'starter':bank(100),'more_recovery':bank(100,recuperators=2),
                                  'premium_recovery':bank(100,recuperators=6,stage='exotic'),
                                  'parallel':bank(200,2,2,2,2),'redundant':bank(200,3,3,3,3)}},indent=2))
