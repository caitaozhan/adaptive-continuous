'''
Implement the paper titled "Adaptive, Continuous Entanglement Generation for Quantum Networks" 
in SeQUeNCe and conduct experiments with a large number of nodes.
'''

import logging
import argparse
from collections import defaultdict
import numpy as np
from sequence.topology.router_net_topo import RouterNetTopo
from sequence.constants import MILLISECOND
import sequence.utils.log as log
from request_app import RequestAppThroughput, RequestAppTimeToServe
from router_net_topo_adaptive import RouterNetTopoAdaptive
from traffic import TrafficMatrix



# linear network topology + entanglement generation (based on 20 samples)
# efficiency = 1:   avg latency = 0.0258s, rate = 38.81/s
# efficiency = 0.5: avg latency = 0.0548s, rate = 18.24/s
# efficiency = 0.1: avg latency = 0.6298s, rate = 1.588/s
def linear_entanglement_generation(verbose=False):
    print('\nLinear, entanglement generation:')

    log_filename = 'log/linear_entanglement_generation'
    # level = logging.DEBUG
    # logging.basicConfig(level=level, filename='', filemode='w')
    
    network_config = 'config/line_2.json'
    # network_config = 'config/random_5.json'
    network_topo = RouterNetTopo(network_config)
    tl = network_topo.get_timeline()

    log.set_logger(__name__, tl, log_filename)
    log.set_logger_level('DEBUG')
    modules = ['timeline', 'network_manager', 'resource_manager', 'rule_manager', 'generation', 'purification', 'swapping', 'bsm']
    for module in modules:
        log.track_module(module)

    src_node_name  = 'router_0'
    dest_node_name = 'router_1'
    src_node = None
    for router in network_topo.get_nodes_by_type(RouterNetTopo.QUANTUM_ROUTER):
        if router.name == src_node_name:
            src_node = router
            break
    
    start_time = 1e12
    end_time   = 10e12
    entanglement_number = 1
    nm = src_node.network_manager
    nm.request(dest_node_name, start_time=start_time, end_time=end_time, memory_size=entanglement_number, target_fidelity=0.8)

    tl.init()
    tl.run()

    latencies = []
    if verbose:
        print(src_node_name, "memories:")
        print("{:5}  {:14}  {:8}  {:>7}".format("Index", "Entangled Node", "Fidelity", "Latency"))
    for info in src_node.resource_manager.memory_manager:
        latency = (info.entangle_time - start_time) * 1e-12
        if latency < 0:
            break
        latencies.append(latency)
        if verbose:
            print("{:5}  {:>14}  {:8.5f}  {:.5f}".format(info.index, str(info.remote_node), float(info.fidelity), latency))
    latency = np.average(latencies)
    print(f'average latency = {latency:.4f}s; rate = {1/latency:.3f}/s')


def linear_swapping(verbose=False):
    print('\nLinear, swapping:')

    log_filename = 'log/linear_swapping'
    # level = logging.DEBUG
    # logging.basicConfig(level=level, filename='', filemode='w')
    
    network_config = 'config/line_5.json'
    # network_config = 'config/random_5.json'
    network_topo = RouterNetTopo(network_config)
    tl = network_topo.get_timeline()

    log.set_logger(__name__, tl, log_filename)
    log.set_logger_level('DEBUG')
    modules = ['timeline', 'network_manager', 'resource_manager', 'rule_manager', 'generation', 'purification', 'swapping', 'bsm']
    for module in modules:
        log.track_module(module)

    src_node_name  = 'router_0'
    dest_node_name = 'router_2'
    src_node = None
    for router in network_topo.get_nodes_by_type(RouterNetTopo.QUANTUM_ROUTER):
        if router.name == src_node_name:
            src_node = router
            break
    
    start_time = 1e12
    end_time   = 10e12
    entanglement_number = 5
    nm = src_node.network_manager
    nm.request(dest_node_name, start_time=start_time, end_time=end_time, memory_size=entanglement_number, target_fidelity=0.8)
    
    # entanglement_number = 2
    # nm = src_node.network_manager
    # start_time = 1e12
    # end_time   = 3e12
    # nm.request(dest_node_name, start_time=start_time, end_time=end_time, memory_size=entanglement_number, target_fidelity=0.8)

    # start_time = 4e12
    # end_time   = 6e12
    # nm.request(dest_node_name, start_time=start_time, end_time=end_time, memory_size=entanglement_number, target_fidelity=0.8)

    # start_time = 2e12
    # end_time   = 5e12
    # nm.request(dest_node_name, start_time=start_time, end_time=end_time, memory_size=entanglement_number, target_fidelity=0.8)

    tl.init()
    tl.run()

    latencies = []
    if verbose:
        print(src_node_name, "memories:")
        print("{:5}  {:14}  {:8}  {:>7}".format("Index", "Entangled Node", "Fidelity", "Latency"))
    for info in src_node.resource_manager.memory_manager:
        latency = (info.entangle_time - start_time) * 1e-12
        if latency < 0:
            break
        latencies.append(latency)
        if verbose:
            print("{:5}  {:>14}  {:8.5f}  {:.5f}".format(info.index, str(info.remote_node), float(info.fidelity), latency))
    latency = np.average(latencies)
    print(f'average latency = {latency:.4f}s; rate = {1/latency:.3f}/s')


# adaptive continuous protocol + one request
def linear_adaptive(verbose=False):
    print('\nLinear, adaptive:')

    network_config = 'config/line_2.json'
    network_topo = RouterNetTopoAdaptive(network_config)
    tl = network_topo.get_timeline()

    log_filename = 'log/linear_adaptive'
    log.set_logger(__name__, tl, log_filename)
    log.set_logger_level('DEBUG')
    modules = ['adaptive_continuous', 'generation', 'bsm', 'timeline', 'rule_manager', 'network_manager', 'resource_manager', 'memory']
    for module in modules:
        log.track_module(module)

    src_node_name  = 'router_0'
    dest_node_name = 'router_1'
    src_node = None
    for router in network_topo.get_nodes_by_type(RouterNetTopo.QUANTUM_ROUTER):
        if router.name == src_node_name:
            src_node = router
            break

    start_time = 0.5e12
    end_time   = 10e12
    entanglement_number = 1
    nm = src_node.network_manager
    nm.request(dest_node_name, start_time=start_time, end_time=end_time, memory_size=entanglement_number, target_fidelity=0.8)

    tl.init()
    tl.run()

    latencies = []
    if verbose:
        print(src_node_name, "memories:")
        print("{:5}  {:14}  {:8}  {:>7}".format("Index", "Entangled Node", "Fidelity", "Latency"))
    for info in src_node.resource_manager.memory_manager:
        latency = (info.entangle_time - start_time) * 1e-12
        if latency < 0:
            break
        latencies.append(latency)
        if verbose:
            print("{:5}  {:>14}  {:8.5f}  {:.5f}".format(info.index, str(info.remote_node), float(info.fidelity), latency))
    latency = np.average(latencies)
    print(f'average latency = {latency:.4f}s; rate = {1/latency:.3f}/s')


# the request app, testing on a two node network
def app_2_node_linear_adaptive(verbose=False):
    
    print('\nLinear, adaptive:')

    network_config = 'config/line_2.json'
    # network_config = 'config/random_5.json'

    log_filename = 'log/linear_adaptive'
    # log_filename = 'log/linear'

    network_topo = RouterNetTopoAdaptive(network_config)
    # network_topo = RouterNetTopo(network_config)
    
    tl = network_topo.get_timeline()

    log.set_logger(__name__, tl, log_filename)
    log.set_logger_level('DEBUG')
    modules = ['adaptive_continuous', 'generation', 'bsm', 'timeline', 'rule_manager', 'network_manager', 'resource_manager', 'memory', 'request_app']
    for module in modules:
        log.track_module(module)

    apps = []
    src_node_name  = 'router_0'
    dest_node_name = 'router_1'
    src_app = None
    for router in network_topo.get_nodes_by_type(RouterNetTopo.QUANTUM_ROUTER):
        app = RequestAppThroughput(router)
        apps.append(app)
        if router.name == src_node_name:
            src_app = app
        router.adaptive_continuous.has_empty_neighbor = False

    start_time = 0.1e12
    end_time   = 5e12
    entanglement_number = 1
    fidelity = 0.6
    src_app.start(dest_node_name, start_time, end_time, entanglement_number, fidelity)

    tl.init()
    tl.run()

    for t in src_app.get_time_to_service():
        print(round(t/1e9), end=', ')
    print()

    for f in src_app.get_fidelity():
        print(f'{f:.5f}', end=', ')
    print()

    request_to_throughput = src_app.get_request_to_throughput()
    for reservation, throughput in request_to_throughput.items():
        print(f'throughput = {throughput:.2f}, reservation = {reservation}')



# the request app, testing on a five node linear network
def app_5_node_linear_adaptive(verbose=False):

    network_config = 'config/line_5.json'

    log_filename = 'log/linear_adaptive'

    network_topo = RouterNetTopoAdaptive(network_config)
    
    tl = network_topo.get_timeline()

    log.set_logger(__name__, tl, log_filename)
    log.set_logger_level('DEBUG')
    modules = ['adaptive_continuous', 'generation', 'bsm', 'timeline', 'rule_manager', 'network_manager', 'resource_manager', 'memory', 'swapping', 'request_app']
    for module in modules:
        log.track_module(module)

    apps = []
    src_node_name  = 'router_1'
    dest_node_name = 'router_3'
    src_app = None
    for router in network_topo.get_nodes_by_type(RouterNetTopo.QUANTUM_ROUTER):
        app = RequestAppThroughput(router)
        apps.append(app)
        if router.name == src_node_name:
            src_app = app

    start_time = 0.1e12
    end_time   = 2e12
    entanglement_number = 1
    fidelity = 0.6
    src_app.start(dest_node_name, start_time, end_time, entanglement_number, fidelity)

    tl.init()
    tl.run()
    print(src_app.get_throughput())
    for t in src_app.get_time_to_service():
        print(round(t/1e9), end=' ')
    print()

    # for t in src_app.get_time_stamps():
    #     print(f'{round(t):,}')
    # print()


# the request app, testing on a five node linear network
def app_5_node_star_adaptive(verbose=False):

    # print('\nLinear, adaptive:')

    network_config = 'config/star_5.json'

    # log_filename = 'log/linear_adaptive'
    log_filename = 'log/time_to_serve-vs-cycle/star,hop=2,qmem=6'

    network_topo = RouterNetTopoAdaptive(network_config)
    
    tl = network_topo.get_timeline()

    log.set_logger(__name__, tl, log_filename)
    log.set_logger_level('INFO')
    # modules = ['timeline', 'network_manager', 'resource_manager', 'rule_manager', 'generation', 
    #            'purification', 'swapping', 'bsm', 'adaptive_continuous', 'memory_manager']
    # modules = ['timeline', 'generation', 'adaptive_continuous', 'request_app', 'rule_manager']
    modules = ['adaptive_continuous', 'request_app', 'swap_memory', 'reservation', 'resource_manager', 'rule_manager', 'generation', 'swapping']
    for module in modules:
        log.track_module(module)

    apps = []
    src_node_name  = 'router_1'
    dest_node_name = 'router_3'
    src_app = None
    for router in network_topo.get_nodes_by_type(RouterNetTopo.QUANTUM_ROUTER):
        app = RequestAppThroughput(router)
        apps.append(app)
        if router.name == src_node_name:
            src_app = app

    start_time = 0.1e12
    end_time   = 10e12
    entanglement_number = 1
    fidelity = 0.6
    src_app.start(dest_node_name, start_time, end_time, entanglement_number, fidelity)

    tl.init()
    tl.run()
    print(src_app.get_throughput())
    for t in src_app.get_time_to_service():
        print(round(t/1e9), end=' ')
    print()

    # for t in src_app.get_time_stamps():
    #     print(f'{round(t):,}')
    # print()


# the request app, testing on a five node linear network
def app_10_node_bottleneck_adaptive(verbose=False):

    # print('\nLinear, adaptive:')

    network_config = 'config/bottleneck_10.json'

    # log_filename = 'log/linear_adaptive'
    log_filename = 'log/time_to_serve-vs-cycle/bottleneck,qmem=6,update=true'

    network_topo = RouterNetTopoAdaptive(network_config)
    
    tl = network_topo.get_timeline()

    log.set_logger(__name__, tl, log_filename)
    log.set_logger_level('INFO')
    # modules = ['timeline', 'network_manager', 'resource_manager', 'rule_manager', 'generation', 
    #            'purification', 'swapping', 'bsm', 'adaptive_continuous', 'memory_manager']
    modules = ['adaptive_continuous', 'request_app']
    # modules = ['adaptive_continuous', 'request_app', 'swap_memory', 'reservation', 'resource_manager', 'rule_manager', 'generation', 'swapping']
    for module in modules:
        log.track_module(module)

    apps = []
    src_node_name  = 'router_0'
    dest_node_name = 'router_6'
    src_app = None
    for router in network_topo.get_nodes_by_type(RouterNetTopo.QUANTUM_ROUTER):
        app = RequestAppThroughput(router)
        apps.append(app)
        if router.name == src_node_name:
            src_app = app

    start_time = 0.1e12
    end_time   = 10e12
    entanglement_number = 1
    fidelity = 0.5
    src_app.start(dest_node_name, start_time, end_time, entanglement_number, fidelity)

    tl.init()
    tl.run()
    print(src_app.get_throughput())
    for t in src_app.get_time_to_service():
        print(round(t/1e9), end=' ')
    print()

    # for t in src_app.get_time_stamps():
    #     print(f'{round(t):,}')
    # print()


# the request app, testing on a ten node bottleneck network, for throughput
def app_10_node_bottleneck_request_queue():

    network_config = 'config/bottleneck_10.json'

    # log_filename = 'log/linear_adaptive'
    log_filename = 'log/queue/bottleneck,qmem=6,update=true,active=4-5,empty-nei=false'

    network_topo = RouterNetTopoAdaptive(network_config)
    
    tl = network_topo.get_timeline()

    log.set_logger(__name__, tl, log_filename)
    log.set_logger_level('INFO')
    # modules = ['timeline', 'network_manager', 'resource_manager', 'rule_manager', 'generation', 
    #            'purification', 'swapping', 'bsm', 'adaptive_continuous', 'memory_manager']
    modules = ['adaptive_continuous', 'request_app', 'swap_memory', 'swapping', 'rule_manager', 'network_manager', 'resource_manager']
    # modules = ['adaptive_continuous', 'request_app', 'swap_memory', 'reservation', 'resource_manager', 'rule_manager', 'generation', 'swapping']
    for module in modules:
        log.track_module(module)

    name_to_apps = {}
    for router in network_topo.get_nodes_by_type(RouterNetTopo.QUANTUM_ROUTER):
        app = RequestAppThroughput(router)
        name_to_apps[router.name] = app
        if router.name not in ['router_4', 'router_5']:
            router.active = False
        router.adaptive_continuous.has_empty_neighbor = False

    num_nodes = len(name_to_apps)
    traffic_matrix = TrafficMatrix(num_nodes)
    traffic_matrix.bottleneck_10()
    request_queue = traffic_matrix.get_request_queue(request_time=3, total_time=31, memo_size=1, fidelity=0.6, entanglement_number=1)
    for request in request_queue:
        id, src_name, dst_name, start_time, end_time, memo_size, fidelity, entanglement_number = request
        app = name_to_apps[src_name]
        app.start(dst_name, start_time, end_time, memo_size, fidelity, entanglement_number, id)

    tl.init()
    tl.run()

    for node_name, app in name_to_apps.items():
        print(node_name)
        request_to_throughput = app.get_request_to_throughput()
        for reservation, throughput in request_to_throughput.items():
            print(f'throughput = {throughput:.2f}, reservation = {reservation}')



# the request type-2 app, testing on a two node linear network, for time-to-serve
def app_2_node_line_request2_queue():

    network_config = 'config/line_2.json'

    # log_filename = 'log/queue_tts/bottleneck,qmem=0'
    log_filename = 'log/queue_tts/line2,qmem=2,update=false'

    network_topo = RouterNetTopoAdaptive(network_config)
    
    tl = network_topo.get_timeline()

    log.set_logger(__name__, tl, log_filename)
    log.set_logger_level('INFO')
    # modules = ['timeline', 'network_manager', 'resource_manager', 'rule_manager', 'generation', 
    #            'purification', 'swapping', 'bsm', 'adaptive_continuous', 'memory_manager']
    modules = ['adaptive_continuous', 'request_app', 'swap_memory', 'swapping', 'rule_manager', 'timeline', 'resource_manager', 'generation', 'main_test']
    # modules = ['adaptive_continuous', 'request_app', 'swap_memory', 'reservation', 'resource_manager', 'rule_manager', 'generation', 'swapping']
    for module in modules:
        log.track_module(module)

    name_to_apps = {}
    for router in network_topo.get_nodes_by_type(RouterNetTopo.QUANTUM_ROUTER):
        app = RequestAppTimeToServe(router)
        name_to_apps[router.name] = app
        # if router.name not in ['router_4', 'router_5']:
        #     router.active = False
        router.adaptive_continuous.has_empty_neighbor = True
        router.adaptive_continuous.update_prob = True

    num_nodes = len(name_to_apps)
    traffic_matrix = TrafficMatrix(num_nodes)
    traffic_matrix.line_2()
    request_queue = traffic_matrix.get_request_queue_tts(request_period=1, total_time=200, memo_size=1, fidelity=0.6, entanglement_number=1)
    for request in request_queue:
        id, src_name, dst_name, start_time, end_time, memo_size, fidelity, entanglement_number = request
        app = name_to_apps[src_name]
        app.start(dst_name, start_time, end_time, memo_size, fidelity, entanglement_number, id)

    tl.init()
    tl.run()

    time_to_serve_dict = defaultdict(float)
    fidelity_dict = defaultdict(list)
    for _, app in name_to_apps.items():
        time_to_serve_dict |= app.time_to_serve
        fidelity_dict |= app.entanglement_fidelities

    for reservation, time_to_serve in sorted(time_to_serve_dict.items()):
        fidelity = fidelity_dict[reservation][0]
        log.logger.info(f'reservation={reservation}, time to serve={time_to_serve / MILLISECOND}, fidelity={fidelity:.6f}')



# the request type-2 app, testing on a ten node bottleneck network, for time-to-serve
def app_10_node_bottleneck_request2_queue():

    network_config = 'config/bottleneck_10.json'

    # log_filename = 'log/queue_tts/bottleneck,qmem=0'
    log_filename = 'log/queue_tts/bottleneck,qmem=5,update=true'

    network_topo = RouterNetTopoAdaptive(network_config)
    
    tl = network_topo.get_timeline()

    log.set_logger(__name__, tl, log_filename)
    log.set_logger_level('INFO')
    # modules = ['timeline', 'network_manager', 'resource_manager', 'rule_manager', 'generation', 
    #            'purification', 'swapping', 'bsm', 'adaptive_continuous', 'memory_manager']
    modules = ['adaptive_continuous', 'request_app', 'swap_memory', 'swapping', 'rule_manager', 'timeline', 'resource_manager', 'generation', 'main']
    # modules = ['adaptive_continuous', 'request_app', 'swap_memory', 'reservation', 'resource_manager', 'rule_manager', 'generation', 'swapping']
    for module in modules:
        log.track_module(module)

    name_to_apps = {}
    for router in network_topo.get_nodes_by_type(RouterNetTopo.QUANTUM_ROUTER):
        app = RequestAppTimeToServe(router)
        name_to_apps[router.name] = app
        # if router.name not in ['router_4', 'router_5']:
        #     router.active = False
        router.adaptive_continuous.has_empty_neighbor = True
        router.adaptive_continuous.update_prob = True

    num_nodes = len(name_to_apps)
    traffic_matrix = TrafficMatrix(num_nodes)
    traffic_matrix.bottleneck_10()
    request_queue = traffic_matrix.get_request_queue_tts(request_period=1, total_time=200, memo_size=1, fidelity=0.6, entanglement_number=1)
    for request in request_queue:
        id, src_name, dst_name, start_time, end_time, memo_size, fidelity, entanglement_number = request
        app = name_to_apps[src_name]
        app.start(dst_name, start_time, end_time, memo_size, fidelity, entanglement_number, id)

    tl.init()
    tl.run()

    time_to_serve_dict = defaultdict(float)
    for _, app in name_to_apps.items():
        time_to_serve_dict |= app.time_to_serve

    for reservation, time_to_serve in sorted(time_to_serve_dict.items()):
        log.logger.info(f'reservation={reservation}, time to serve={time_to_serve / MILLISECOND}')



# the request type-2 app, testing on a twenty node bottleneck network, for time-to-serve
def app_20_node_bottleneck_request2_queue():

    network_config = 'config/bottleneck_20.json'

    # log_filename = 'log/queue_tts/bottleneck20,qmem=0'
    log_filename = 'log/queue_tts/bottleneck20,qmem=5,update=true,tmp'

    network_topo = RouterNetTopoAdaptive(network_config)
    
    tl = network_topo.get_timeline()

    log.set_logger(__name__, tl, log_filename)
    log.set_logger_level('INFO')
    # modules = ['timeline', 'network_manager', 'resource_manager', 'rule_manager', 'generation', 
    #            'purification', 'swapping', 'bsm', 'adaptive_continuous', 'memory_manager']
    modules = ['adaptive_continuous', 'request_app', 'swapping', 'network_manager', 'resource_manager', 'main', 'rule_manager', 'generation', 'swapping']
    # modules = ['adaptive_continuous', 'request_app', 'swap_memory', 'reservation', 'resource_manager', 'rule_manager', 'generation', 'swapping']
    for module in modules:
        log.track_module(module)

    name_to_apps = {}
    for router in network_topo.get_nodes_by_type(RouterNetTopo.QUANTUM_ROUTER):
        app = RequestAppTimeToServe(router)
        name_to_apps[router.name] = app
        # if router.name not in ['router_4', 'router_5']:
        #     router.active = False
        router.adaptive_continuous.has_empty_neighbor = True
        router.adaptive_continuous.update_prob = True

    num_nodes = len(name_to_apps)
    traffic_matrix = TrafficMatrix(num_nodes)
    traffic_matrix.bottleneck_20()
    request_queue = traffic_matrix.get_request_queue_tts(request_period=1, total_time=200, memo_size=1, fidelity=0.6, entanglement_number=1)
    for request in request_queue:
        id, src_name, dst_name, start_time, end_time, memo_size, fidelity, entanglement_number = request
        app = name_to_apps[src_name]
        app.start(dst_name, start_time, end_time, memo_size, fidelity, entanglement_number, id)

    tl.init()
    tl.run()

    time_to_serve_dict = defaultdict(float)
    for _, app in name_to_apps.items():
        time_to_serve_dict |= app.time_to_serve

    for reservation, time_to_serve in sorted(time_to_serve_dict.items()):
        log.logger.info(f'reservation={reservation}, time to serve={time_to_serve / MILLISECOND}')



# the request type-2 app, testing on a twenty node bottleneck network, for time-to-serve
def app_20_node_as_request2_queue():

    update_prob = True

    network_config = 'config/as_20.json'

    # log_filename = 'log/queue_tts/as20,qmem=0'
    log_filename = f'log/queue_tts/as20,qmem=5,update={update_prob}'

    network_topo = RouterNetTopoAdaptive(network_config)
    
    tl = network_topo.get_timeline()

    log.set_logger(__name__, tl, log_filename)
    log.set_logger_level('INFO')
    # modules = ['timeline', 'network_manager', 'resource_manager', 'rule_manager', 'generation', 
    #            'purification', 'swapping', 'bsm', 'adaptive_continuous', 'memory_manager']
    modules = ['adaptive_continuous', 'request_app', 'swapping', 'network_manager', 'resource_manager', 'main', 'rule_manager', 'generation', 'swapping', 'timeline']
    # modules = ['adaptive_continuous', 'request_app', 'swap_memory', 'reservation', 'resource_manager', 'rule_manager', 'generation', 'swapping']
    for module in modules:
        log.track_module(module)

    name_to_apps = {}
    for router in network_topo.get_nodes_by_type(RouterNetTopo.QUANTUM_ROUTER):
        app = RequestAppTimeToServe(router)
        name_to_apps[router.name] = app
        # if router.name not in ['router_4', 'router_5']:
        #     router.active = False
        router.adaptive_continuous.has_empty_neighbor = True
        router.adaptive_continuous.update_prob = update_prob

    num_nodes = len(name_to_apps)
    traffic_matrix = TrafficMatrix(num_nodes)
    traffic_matrix.as_20()
    request_queue = traffic_matrix.get_request_queue_tts(request_period=1, total_time=200, memo_size=1, fidelity=0.6, entanglement_number=1)
    for request in request_queue:
        id, src_name, dst_name, start_time, end_time, memo_size, fidelity, entanglement_number = request
        app = name_to_apps[src_name]
        app.start(dst_name, start_time, end_time, memo_size, fidelity, entanglement_number, id)

    tl.init()
    tl.run()

    time_to_serve_dict = defaultdict(float)
    for _, app in name_to_apps.items():
        time_to_serve_dict |= app.time_to_serve

    for reservation, time_to_serve in sorted(time_to_serve_dict.items()):
        log.logger.info(f'reservation={reservation}, time to serve={time_to_serve / MILLISECOND}')


# the request type-2 app, testing on a twenty node bottleneck network, for time-to-serve
def app_100_node_as_request2_queue():

    update_prob = True
    memory_adaptive = 5

    network_config = 'config/as_100.json'

    log_filename = f'log/queue_tts/as100,qmem={memory_adaptive},update={update_prob}'

    network_topo = RouterNetTopoAdaptive(network_config)
    
    tl = network_topo.get_timeline()

    log.set_logger(__name__, tl, log_filename)
    log.set_logger_level('INFO')
    # modules = ['timeline', 'network_manager', 'resource_manager', 'rule_manager', 'generation', 
    #            'purification', 'swapping', 'bsm', 'adaptive_continuous', 'memory_manager']
    modules = ['adaptive_continuous', 'request_app', 'network_manager', 'resource_manager', 'main_test']
    # modules = ['adaptive_continuous', 'request_app', 'swap_memory', 'reservation', 'resource_manager', 'rule_manager', 'generation', 'swapping']
    for module in modules:
        log.track_module(module)

    name_to_apps = {}
    for router in network_topo.get_nodes_by_type(RouterNetTopo.QUANTUM_ROUTER):
        app = RequestAppTimeToServe(router)
        name_to_apps[router.name] = app
        # if router.name not in ['router_4', 'router_5']:
        #     router.active = False
        router.adaptive_continuous.has_empty_neighbor = True
        router.adaptive_continuous.update_prob = update_prob
        router.adaptive_continuous.set_adaptive_max_memory(memory_adaptive)      

    num_nodes = len(name_to_apps)
    traffic_matrix = TrafficMatrix(num_nodes)
    traffic_matrix.as_100()
    # traffic_matrix.as_100_()
    request_queue = traffic_matrix.get_request_queue_tts(request_period=1, total_time=10, memo_size=1, fidelity=0.6, entanglement_number=1)
    print(request_queue)
    for request in request_queue:
        id, src_name, dst_name, start_time, end_time, memo_size, fidelity, entanglement_number = request
        app = name_to_apps[src_name]
        app.start(dst_name, start_time, end_time, memo_size, fidelity, entanglement_number, id)

    tl.init()
    tl.run()

    time_to_serve_dict = defaultdict(float)
    for _, app in name_to_apps.items():
        time_to_serve_dict |= app.time_to_serve

    for reservation, time_to_serve in sorted(time_to_serve_dict.items()):
        log.logger.info(f'reservation={reservation}, time to serve={time_to_serve / MILLISECOND}')



if __name__ == '__main__':
    verbose = True
    # linear_entanglement_generation(verbose)
    # linear_swapping(verbose)
    # linear_adaptive(verbose)
    # app_2_node_linear_adaptive(verbose)

    app_5_node_linear_adaptive(verbose)

    # app_5_node_star_adaptive(verbose)
    # app_10_node_bottleneck_adaptive(verbose)
    # app_10_node_bottleneck_request_queue()
    # app_2_node_line_request2_queue()
    # app_10_node_bottleneck_request2_queue()
    # app_20_node_as_request2_queue()
    # app_100_node_as_request2_queue()

