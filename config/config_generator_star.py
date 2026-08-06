"""This module generates JSON config files for networks in a star configuration.

Help information may also be obtained using the `-h` flag.

Args:
    star_size (int): number of non-center network nodes (network size is star_size+1).
    memo_size_center (int): number of memories on the center node.
    memo_size (int): number of memories per end node.
    qc_length (float): distance between nodes (in km).
    qc_atten (float): quantum channel attenuation (in dB/m).
    cc_delay (float): classical channel delay (in ms).

Optional Args:
    -d --directory (str): name of the output directory (default config).
    -o --output (str): name of the output file (default star.json).
    -s --stop (float): simulation stop time (in s) (default infinity).

python config/config_generator_star.py 5 20 10 1 0.0002 1 -o star_5.json -s 10
"""

import argparse
import json
import os

from sequence.constants import SECOND
from sequence.topology.topology import Topology
from sequence.topology.router_net_topo import RouterNetTopo


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('star_size', type=int, help='number of non-center network nodes')
    parser.add_argument('memo_size_center', type=int, help='number of memories on center node')
    parser.add_argument('memo_size', type=int, help='number of memories per node')
    parser.add_argument('qc_length', type=float, help='distance between nodes (in km)')
    parser.add_argument('qc_atten', type=float, help='quantum channel attenuation (in dB/m)')
    parser.add_argument('cc_delay', type=float, help='classical channel delay (in ms)')
    parser.add_argument('-d', '--directory', type=str, default='config', help='name of output directory')
    parser.add_argument('-o', '--output', type=str, default='star.json', help='name of output config file')
    parser.add_argument('-s', '--stop', type=float, default=float('inf'), help='stop time (in s)')
    args = parser.parse_args()

    templates = {
        "router_template": {
            "MemoryArray": {
                "fidelity": 0.98,
                "efficiency": 0.5
            },
            "adaptive_max_memory": 2
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

    center_name = "router_center"
    router_names = [f"router_{i}" for i in range(args.star_size)] + [center_name]

    nodes = []
    for i, name in enumerate(router_names):
        config = {Topology.NAME: name,
                  Topology.TYPE: RouterNetTopo.QUANTUM_ROUTER,
                  Topology.SEED: i,
                  RouterNetTopo.MEMO_ARRAY_SIZE: args.memo_size,
                  RouterNetTopo.TEMPLATE: "router_template"}
        if name == center_name:
            config[RouterNetTopo.MEMO_ARRAY_SIZE] = args.memo_size_center
        nodes.append(config)

    bsm_names = [f"BSM_{i}" for i in range(args.star_size)]
    bsm_nodes = [{Topology.NAME: bsm_name,
                  Topology.TYPE: RouterNetTopo.BSM_NODE,
                  Topology.SEED: i,
                  RouterNetTopo.TEMPLATE: "bsm_template"}
                 for i, bsm_name in enumerate(bsm_names)]

    qchannels = []
    cchannels = []
    for node_name, bsm_name in zip(router_names[:-1], bsm_names):
        qchannels.append({Topology.SRC: node_name,
                          Topology.DST: bsm_name,
                          Topology.DISTANCE: args.qc_length * 500,
                          Topology.ATTENUATION: args.qc_atten})
        qchannels.append({Topology.SRC: center_name,
                          Topology.DST: bsm_name,
                          Topology.DISTANCE: args.qc_length * 500,
                          Topology.ATTENUATION: args.qc_atten})
        for node in [node_name, center_name]:
            cchannels.append({Topology.SRC: node,
                              Topology.DST: bsm_name,
                              Topology.DELAY: args.cc_delay * 1e9})
            cchannels.append({Topology.SRC: bsm_name,
                              Topology.DST: node,
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
                   Topology.STOP_TIME: int(args.stop * SECOND)}

    path = os.path.join(args.directory, args.output)
    with open(path, 'w') as f:
        json.dump(output_dict, f, indent=4)


if __name__ == '__main__':
    main()
