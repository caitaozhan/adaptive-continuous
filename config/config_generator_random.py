"""This module generates JSON config files for a random network.

Help information may also be obtained using the `-h` flag.

Args:
    net_size (int): number of nodes in the random network.
    memo_size (int): number of memories per node.
    qc_length (float): distance between nodes (in km).
    qc_atten (float): quantum channel attenuation (in dB/m).
    cc_delay (float): classical channel delay (in ms).

Optional Args:
    -d --directory (str): name of the output directory (default config).
    -o --output (str): name of the output file (default random.json).
    -s --stop (float): simulation stop time (in s) (default infinity).

python config/config_generator_random.py 10 10 10 0.0002 1 -o random_10.json -s 10
"""

import argparse
import json
import os
import random
from typing import Tuple

import numpy as np
from networkx.generators.geometric import waxman_graph

from sequence.constants import SECOND
from sequence.topology.topology import Topology
from sequence.topology.router_net_topo import RouterNetTopo


def create_random_waxman(area_length: int, number_nodes: int, edge_density: float) -> Tuple[list, list]:
    '''create a random network using waxman
    Return:
        a list of vertex in (x, y), where x, y are real number geographic coordinates
        a list of edges in (u, v), where u, v are integer vertex index
    '''
    max_number_edges = (number_nodes - 1) * number_nodes // 2
    alpa_min, alpha_max = 0, 100
    while alpha_max - alpa_min > 0.001:
        alpha = (alpa_min + alpha_max) / 2
        graphx_list = []
        for _ in range(10):  # do average of 10
            graphx_list.append(waxman_graph(number_nodes, domain=(0, 0, area_length, area_length), beta=1, alpha=alpha)) # cannot understand the L parameter
        avg_length = np.average([len(graphx.edges()) for graphx in graphx_list])
        
        if (edge_density - 0.002) * max_number_edges <= avg_length <= (edge_density + 0.002) * max_number_edges:
            break
        elif avg_length > (edge_density + 0.002) * max_number_edges:
            alpha_max = alpha
        else:
            alpa_min = alpha
    # pick the best one of the 10
    target = edge_density * max_number_edges
    graphx = None
    difference = float('inf')
    for tmp_graphx in graphx_list:
        diff = abs(len(tmp_graphx.edges()) - target)
        if diff < difference:
            graphx = tmp_graphx
            difference = diff

    V = [(round(graphx.nodes[i]["pos"][0], 2), round(graphx.nodes[i]["pos"][1], 2)) for i in range(number_nodes)]

    E = list(graphx.edges())

    print(f'number of nodes = {len(V)}')
    print(f'# of edge = {len(graphx.edges())}, edge density = {len(graphx.edges())/max_number_edges:.4f}')
    return V, E


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('net_size', type=int, help='number of network nodes')
    parser.add_argument('memo_size', type=int, help='number of memories per node')
    parser.add_argument('qc_length', type=float, help='distance between nodes (in km)')
    parser.add_argument('qc_atten', type=float, help='quantum channel attenuation (in dB/m)')
    parser.add_argument('cc_delay', type=float, help='classical channel delay (in ms)')
    parser.add_argument('-d', '--directory', type=str, default='config', help='name of output directory')
    parser.add_argument('-o', '--output', type=str, default='random.json', help='name of output config file')
    parser.add_argument('-s', '--stop', type=float, default=float('inf'), help='stop time (in s)')
    args = parser.parse_args()

    net_size = args.net_size
    area_length = 1000
    edge_density = 0.8

    random.seed(0)
    np.random.seed(0)
    V, E = create_random_waxman(area_length, net_size, edge_density)

    router_names = [f"router_{i}" for i in range(net_size)]
    nodes = [{Topology.NAME: name,
              Topology.TYPE: RouterNetTopo.QUANTUM_ROUTER,
              Topology.SEED: i,
              RouterNetTopo.MEMO_ARRAY_SIZE: args.memo_size}
             for i, name in enumerate(router_names)]

    qchannels = []
    cchannels = []
    bsm_nodes = []
    seed = 0
    for node1, node2 in E:
        node1_name = router_names[node1]
        node2_name = router_names[node2]
        node1_loc = V[node1]
        node2_loc = V[node2]
        distance = np.sqrt((node1_loc[0] - node2_loc[0]) ** 2 + (node1_loc[1] - node2_loc[1]) ** 2)

        bsm_name = f"BSM_{node1_name}_{node2_name}"
        bsm_nodes.append({Topology.NAME: bsm_name,
                          Topology.TYPE: RouterNetTopo.BSM_NODE,
                          Topology.SEED: seed})

        # qchannels
        qchannels.append({Topology.SRC: node1_name,
                          Topology.DST: bsm_name,
                          Topology.DISTANCE: round(distance / 2, 2),
                          Topology.ATTENUATION: args.qc_atten})
        qchannels.append({Topology.SRC: node2_name,
                          Topology.DST: bsm_name,
                          Topology.DISTANCE: round(distance / 2, 2),
                          Topology.ATTENUATION: args.qc_atten})
        # cchannels
        cchannels.append({Topology.SRC: node1_name,
                          Topology.DST: bsm_name,
                          Topology.DELAY: args.cc_delay * 1e9})
        cchannels.append({Topology.SRC: node2_name,
                          Topology.DST: bsm_name,
                          Topology.DELAY: args.cc_delay * 1e9})
        cchannels.append({Topology.SRC: bsm_name,
                          Topology.DST: node1_name,
                          Topology.DELAY: args.cc_delay * 1e9})
        cchannels.append({Topology.SRC: bsm_name,
                          Topology.DST: node2_name,
                          Topology.DELAY: args.cc_delay * 1e9})
        seed += 1

    # 2. generate classical links between all node pairs
    for i, node1_name in enumerate(router_names):
        for node2_name in router_names[i+1:]:
            cchannels.append({Topology.SRC: node1_name,
                              Topology.DST: node2_name,
                              Topology.DELAY: args.cc_delay * 1e9})
            cchannels.append({Topology.SRC: node2_name,
                              Topology.DST: node1_name,
                              Topology.DELAY: args.cc_delay * 1e9})

    output_dict = {Topology.ALL_NODE: nodes + bsm_nodes,
                   Topology.ALL_Q_CHANNEL: qchannels,
                   Topology.ALL_C_CHANNEL: cchannels,
                   Topology.STOP_TIME: int(args.stop * SECOND)}

    path = os.path.join(args.directory, args.output)
    with open(path, 'w') as f:
        json.dump(output_dict, f, indent=4)


if __name__ == '__main__':
    main()
