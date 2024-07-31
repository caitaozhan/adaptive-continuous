'''
Implement the paper titled "Adaptive, Continuous Entanglement Generation for Quantum Networks" 
in SeQUeNCe and conduct experiments with a large number of nodes.
'''

import logging
import argparse
import numpy as np
from sequence.topology.router_net_topo import RouterNetTopo
import sequence.utils.log as log
from request_app import RequestAppAdaptive
from router_net_topo_adaptive import RouterNetTopoAdaptive


# linear network topology + entanglement generation
# efficiency = 1:   avg latency = 0.0298s, rate = 33.59/s
# efficiency = 0.5: avg latency = 0.0851s, rate = 11.76/s
# efficiency = 0.1: avg latency = 1.4237s, rate = 0.702/s
def linear_entanglement_generation(verbose=False):
    print('\nLinear, entanglement generation:')

    log_filename = 'log/linear_entanglement_generation'
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


# linear network topology + swapping
# efficiency = 1:   avg latency = 0.0648s, rate = 15.44/s
# efficiency = 0.5: avg latency = 0.1517s, rate = 6.591/s
# efficiency = 0.1: avg latency = 3.4507s, rate = 0.290/s
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

    log_filename = 'log/linear_adaptive'
    # level = logging.DEBUG
    # logging.basicConfig(level=level, filename='', filemode='w')
    
    network_config = 'config/line_2.json'
    # network_config = 'config/random_5.json'
    network_topo = RouterNetTopoAdaptive(network_config)
    tl = network_topo.get_timeline()

    log.set_logger(__name__, tl, log_filename)
    log.set_logger_level('DEBUG')
    # modules = ['timeline', 'network_manager', 'resource_manager', 'rule_manager', 'generation', 
    #            'purification', 'swapping', 'bsm', 'adaptive_continuous', 'memory_manager']
    modules = ['timeline', 'network_manager', 'rule_manager', 'adaptive_continuous_protocol', \
               'resource_manager', 'generation', 'swap_memory_protocol']
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
    end_time   = 1.5e12
    entanglement_number = 1
    nm = src_node.network_manager
    nm.request(dest_node_name, start_time=start_time, end_time=end_time, memory_size=entanglement_number, target_fidelity=0.8)

    tl.init()
    tl.run()


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
    # modules = ['timeline', 'network_manager', 'resource_manager', 'rule_manager', 'generation', 
    #            'purification', 'swapping', 'bsm', 'adaptive_continuous', 'memory_manager']
    modules = ['timeline', 'generation', 'adaptive_continuous', 'request_app', 'rule_manager', 'swap_memory']
    for module in modules:
        log.track_module(module)

    apps = []
    src_node_name  = 'router_0'
    dest_node_name = 'router_1'
    src_app = None
    for router in network_topo.get_nodes_by_type(RouterNetTopo.QUANTUM_ROUTER):
        app = RequestAppAdaptive(router)
        apps.append(app)
        if router.name == src_node_name:
            src_app = app

    start_time = 0.5e12
    end_time   = 3.5e12
    entanglement_number = 1
    fidelity = 0.6
    src_app.start(dest_node_name, start_time, end_time, entanglement_number, fidelity)

    tl.init()
    tl.run()
    print(src_app.get_throughput())
    for t in src_app.get_time_to_service():
        print(round(t/1e9), end=' ')
    print()



# the request app, testing on a five node linear network
def app_5_node_linear_adaptive(verbose=False):

    # print('\nLinear, adaptive:')

    network_config = 'config/line_5.json'

    # log_filename = 'log/linear_adaptive'
    log_filename = 'log/time_to_serve-vs-cycle/linear,hop=2,qmem=2'

    network_topo = RouterNetTopoAdaptive(network_config)
    
    tl = network_topo.get_timeline()

    log.set_logger(__name__, tl, log_filename)
    log.set_logger_level('DEBUG')
    # modules = ['timeline', 'network_manager', 'resource_manager', 'rule_manager', 'generation', 
    #            'purification', 'swapping', 'bsm', 'adaptive_continuous', 'memory_manager']
    # modules = ['timeline', 'generation', 'adaptive_continuous', 'request_app', 'rule_manager']
    modules = ['adaptive_continuous', 'request_app', 'swap_memory', 'reservation', 'resource_manager', 'rule_manager']
    for module in modules:
        log.track_module(module)

    apps = []
    src_node_name  = 'router_1'
    dest_node_name = 'router_3'
    src_app = None
    for router in network_topo.get_nodes_by_type(RouterNetTopo.QUANTUM_ROUTER):
        app = RequestAppAdaptive(router)
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



if __name__ == '__main__':
    verbose = True
    # linear_entanglement_generation(verbose)
    # linear_swapping(verbose)
    # linear_adaptive(verbose)
    # app_2_node_linear_adaptive(verbose)
    app_5_node_linear_adaptive(verbose)

