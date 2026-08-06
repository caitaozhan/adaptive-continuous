"""This module generates JSON config files for networks in a bottleneck configuration, shown as follows:

(left) -- node -- node -- (right)

Help information may also be obtained using the `-h` flag.

Args:
    left_size (int): number of nodes on the left side of the bottleneck.
    right_size (int): number of nodes on the right side of the bottleneck.
    memo_size_bottleneck (int): number of memories on the bottleneck node.
    memo_size_side (int): number of memories on the side nodes.
    qc_length (float): distance between nodes (in km).
    qc_atten (float): quantum channel attenuation (in dB/m).
    cc_delay (float): classical channel delay (in ms).

Optional Args:
    -d --directory (str): name of the output directory (default config).
    -o --output (str): name of the output file (default bottleneck.json).
    -s --stop (float): simulation stop time (in s) (default infinity).

python config/config_generator_bottleneck.py 4 4 10 5 1 0.0002 1 -o bottleneck_10.json -s 10
python config/config_generator_bottleneck.py 9 9 10 10 10 0.0002 1 -o bottleneck_20.json -s 10
"""

import argparse
import json
import os

from sequence.constants import BELL_DIAGONAL_STATE_FORMALISM, SECOND
from sequence.topology.topology import Topology
from sequence.topology.router_net_topo import RouterNetTopo


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('left_size', type=int, help='number of nodes on the left side of the bottleneck')
    parser.add_argument('right_size', type=int, help='number of nodes on the right side of the bottleneck')
    parser.add_argument('memo_size_bottleneck', type=int, help='number of memories on the bottleneck node')
    parser.add_argument('memo_size_side', type=int, help='number of memories on the side node')
    parser.add_argument('qc_length', type=float, help='distance between nodes (in km)')
    parser.add_argument('qc_atten', type=float, help='quantum channel attenuation (in dB/m)')
    parser.add_argument('cc_delay', type=float, help='classical channel delay (in ms)')
    parser.add_argument('-d', '--directory', type=str, default='config', help='name of output directory')
    parser.add_argument('-o', '--output', type=str, default='bottleneck.json', help='name of output config file')
    parser.add_argument('-s', '--stop', type=float, default=float('inf'), help='stop time (in s)')
    args = parser.parse_args()

    templates = {
        "router_template": {
            "MemoryArray": {
                "fidelity": 0.95,
                "efficiency": 0.6,
                "coherence_time": 2,
                "decoherence_errors": [0.3333333333333333, 0.3333333333333333, 0.3333333333333333]
            },
            "adaptive_max_memory": 0
        },
        "bsm_template": {
            "encoding_type": "single_heralded",
            "SingleHeraldedBSM": {
                "detectors": [
                    {"efficiency": 0.95},
                    {"efficiency": 0.95}
                ]
            }
        }
    }

    net_size = args.left_size + args.right_size + 2
    bottleneck_left_name = f"router_{args.left_size}"
    bottleneck_right_name = f"router_{args.left_size + 1}"

    router_names = [f"router_{i}" for i in range(net_size)]
    nodes = []
    for i, name in enumerate(router_names):
        config = {Topology.NAME: name,
                  Topology.TYPE: RouterNetTopo.QUANTUM_ROUTER,
                  Topology.SEED: i,
                  RouterNetTopo.MEMO_ARRAY_SIZE: args.memo_size_side,
                  RouterNetTopo.TEMPLATE: "router_template"}
        if name in (bottleneck_left_name, bottleneck_right_name):
            config[RouterNetTopo.MEMO_ARRAY_SIZE] = args.memo_size_bottleneck
        nodes.append(config)

    channels = []  # [(left node, bsm, right node), ...]
    for i in range(args.left_size):
        bsm_name = f"BSM_{i}_{args.left_size}"
        channels.append((router_names[i], bsm_name, bottleneck_left_name))

    bsm_name = f"BSM_{args.left_size}_{args.left_size + 1}"
    channels.append((router_names[args.left_size], bsm_name, router_names[args.left_size + 1]))

    for i in range(args.left_size + 2, args.left_size + 2 + args.right_size):
        bsm_name = f"BSM_{args.left_size + 1}_{i}"
        channels.append((bottleneck_right_name, bsm_name, router_names[i]))

    bsm_nodes = [{Topology.NAME: bsm_name,
                  Topology.TYPE: RouterNetTopo.BSM_NODE,
                  Topology.SEED: i,
                  RouterNetTopo.TEMPLATE: "bsm_template"}
                 for i, (_, bsm_name, _) in enumerate(channels)]

    qchannels = []
    cchannels = []
    for left_node_name, bsm_name, right_node_name in channels:
        qchannels.append({Topology.SRC: left_node_name,
                          Topology.DST: bsm_name,
                          Topology.DISTANCE: args.qc_length * 1000 / 2,
                          Topology.ATTENUATION: args.qc_atten})
        qchannels.append({Topology.SRC: right_node_name,
                          Topology.DST: bsm_name,
                          Topology.DISTANCE: args.qc_length * 1000 / 2,
                          Topology.ATTENUATION: args.qc_atten})
        for node in (left_node_name, right_node_name):
            cchannels.append({Topology.SRC: node,
                              Topology.DST: bsm_name,
                              Topology.DISTANCE: args.qc_length * 1000 / 2,
                              Topology.DELAY: args.cc_delay * 1e9})
            cchannels.append({Topology.SRC: bsm_name,
                              Topology.DST: node,
                              Topology.DISTANCE: args.qc_length * 1000 / 2,
                              Topology.DELAY: args.cc_delay * 1e9})

    for node1 in router_names:
        for node2 in router_names:
            if node1 == node2:
                continue
            cchannels.append({Topology.SRC: node1,
                              Topology.DST: node2,
                              Topology.DELAY: args.cc_delay * 1e9})

    output_dict = {Topology.ALL_TEMPLATES: templates,
                   Topology.ALL_NODE: nodes + bsm_nodes,
                   Topology.ALL_Q_CHANNEL: qchannels,
                   Topology.ALL_C_CHANNEL: cchannels,
                   Topology.STOP_TIME: int(args.stop * SECOND),
                   Topology.FORMALISM: BELL_DIAGONAL_STATE_FORMALISM}

    path = os.path.join(args.directory, args.output)
    with open(path, 'w') as f:
        json.dump(output_dict, f, indent=4)


if __name__ == '__main__':
    main()
