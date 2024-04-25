'''
Implement the paper titled "Adaptive, Continuous Entanglement Generation for Quantum Networks" 
in SeQUeNCe and conduct experiments with a large number of nodes.
'''

import logging
import argparse

from sequence.topology.router_net_topo import RouterNetTopo


def main():

    level = logging.DEBUG
    logging.basicConfig(level=level, filename='', filemode='w')
    
    network_config = 'config/line_5.json'
    # network_config = 'config/random_5.json'
    network_topo = RouterNetTopo(network_config)
    tl = network_topo.get_timeline()

    src_node_name  = 'router_0'
    dest_node_name = 'router_2'
    src_node = None
    for router in network_topo.get_nodes_by_type(RouterNetTopo.QUANTUM_ROUTER):
        if router.name == src_node_name:
            src_node = router
            break
    
    nm = src_node.network_manager
    nm.request(dest_node_name, start_time=1e12, end_time=10e12, memory_size=1, target_fidelity=0.8)
    # random_5.json, why 0 start time won't work?
    # line_5.json, why no entanglement?

    tl.init()
    tl.run()

    print(src_node_name, "memories")
    print("Index:\tEntangled Node:\tFidelity:\tEntanglement Time:")
    for info in src_node.resource_manager.memory_manager:
        print("{:6}\t{:10}\t{:.4}\t{}".format(info.index, str(info.remote_node), float(info.fidelity), str(info.entangle_time * 1e-12)))


if __name__ == '__main__':

    main()
