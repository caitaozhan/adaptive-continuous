"""the main
"""

import argparse
import os
from collections import defaultdict

import sequence.utils.log as log
from sequence.constants import MILLISECOND, SECOND

from router_net_topo_adaptive import RouterNetTopoAdaptive
from request_app import RequestAppTimeToServe
from traffic import TrafficMatrix


def main():
    parser = argparse.ArgumentParser(description='Parameters for Adaptive Continuous Protocol simulation')
    parser.add_argument('-tp', '--topology', type=str, default='line', help='topology, i.e. line, bottleneck, as')
    parser.add_argument('-n', '--node', type=int, default=5, help='number of nodes in the quantum network')
    parser.add_argument('-t', '--time', type=int, default=10, help='simulation time in seconds')
    parser.add_argument('-ns', '--node_seed', type=int, default=0, help='related to the random seed of the node')
    parser.add_argument('-qs', '--queue_seed', type=int, default=0, help='related to the random seed of the queue')
    parser.add_argument('-ma', '--memory_adaptive', type=int, default=5, help='number of memory per node used by the adaptive continuous protocol')
    parser.add_argument('-up', '--update_prob', action='store_true', help='whether to update the probability table or not')
    parser.add_argument('-d', '--log_directory', type=str, default='log', help='the directory of the log')
    parser.add_argument('-s', '--strategy', type=str, default='freshest', help='the strategy of selecting one of the multiple entanglement pairs')

    args = parser.parse_args()
    topology = args.topology
    node     = args.node
    time     = args.time
    node_seed       = args.node_seed
    queue_seed      = args.queue_seed
    memory_adaptive = args.memory_adaptive
    update_prob     = args.update_prob
    log_directory   = args.log_directory
    strategy        = args.strategy

    if os.path.exists(log_directory) is False:
        os.mkdir(log_directory)

    network_config = f'config/{topology}_{node}.json'
    network_topo = RouterNetTopoAdaptive(network_config)
    network_topo.update_stop_time(time * SECOND)
    tl = network_topo.get_timeline()

    log_filename = f'{log_directory}/{topology}{node},ma={memory_adaptive},up={update_prob},ns={node_seed},qs={queue_seed},s={strategy}'
    log.set_logger(__name__, tl, log_filename)
    log.set_logger_level('INFO')
    modules = ['main']
    for module in modules:
        log.track_module(module)

    name_to_apps = {}
    for router in network_topo.get_nodes_by_type(RouterNetTopoAdaptive.QUANTUM_ROUTER):
        router.set_seed(router.get_seed() + node_seed)
        router.adaptive_continuous.set_adaptive_max_memory(memory_adaptive)        

        app = RequestAppTimeToServe(router)
        name_to_apps[router.name] = app
        router.adaptive_continuous.has_empty_neighbor = True
        router.adaptive_continuous.update_prob = update_prob
        router.adaptive_continuous.strategy = strategy

    for bsm_node in network_topo.get_nodes_by_type(RouterNetTopoAdaptive.BSM_NODE):
        bsm_node.set_seed(bsm_node.get_seed() + node_seed)

    traffic_matrix = TrafficMatrix(node)
    traffic_matrix.set(topology, node)
    
    request_queue = traffic_matrix.get_request_queue_tts(request_period=1, total_time=time, memo_size=1, fidelity=0.5, entanglement_number=1, seed=queue_seed)
    for request in request_queue:
        id, src_name, dst_name, start_time, end_time, memo_size, fidelity, entanglement_number = request
        app = name_to_apps[src_name]
        app.start(dst_name, start_time, end_time, memo_size, fidelity, entanglement_number, id)

    tl.init()
    tl.run()

    time_to_serve_dict = defaultdict(float)
    fidelity_dict = defaultdict(float)
    for _, app in name_to_apps.items():
        time_to_serve_dict |= app.time_to_serve
        fidelity_dict |= app.entanglement_fidelities

    for reservation, time_to_serve in sorted(time_to_serve_dict.items()):
        fidelity = fidelity_dict[reservation][0]
        log.logger.info(f'reservation={reservation}, time to serve={time_to_serve / MILLISECOND}, fidelity={fidelity:.6f}')





if __name__ == '__main__':
    main()
