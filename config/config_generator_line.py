"""This module generates JSON config files for networks in a linear configuration.

Help information may also be obtained using the `-h` flag.

Args:
    linear_size (int): number of nodes in the graph.
    memo_size (int): number of memories per node.
    qc_length (float): distance between nodes (in km).
    qc_atten (float): quantum channel attenuation (in dB/m).
    cc_delay (float): classical channel delay (in ms).

Optional Args:
    -d --directory (str): name of the output directory (default config).
    -o --output (str): name of the output file (default line.json).
    -s --stop (float): simulation stop time (in s) (default infinity).
    -gf --gate_fidelity (float): fidelity of two-qubit gates.
    -mf --measurement_fidelity (float): fidelity of measurements.

python config/config_generator_line.py 2 10 10 0.0002 1 -o line_2.json -s 10 -gf 0.99 -mf 0.99
python config/config_generator_line.py 5 10 1 0.0002 1 -o line_5.json -s 10 -gf 0.99 -mf 0.99
"""

import argparse
import json
import os

from sequence.constants import BELL_DIAGONAL_STATE_FORMALISM, MILLISECOND, SECOND
from sequence.topology.topology import Topology
from sequence.topology.router_net_topo import RouterNetTopo


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('linear_size', type=int, help='number of network nodes')
    parser.add_argument('memo_size', type=int, help='number of memories per node')
    parser.add_argument('qc_length', type=float, help='distance between nodes (in km)')
    parser.add_argument('qc_atten', type=float, help='quantum channel attenuation (in dB/m)')
    parser.add_argument('cc_delay', type=float, help='classical channel delay (in ms)')
    parser.add_argument('-d', '--directory', type=str, default='config', help='name of output directory')
    parser.add_argument('-o', '--output', type=str, default='line.json', help='name of output config file')
    parser.add_argument('-s', '--stop', type=float, default=float('inf'), help='stop time (in s)')
    parser.add_argument('-gf', '--gate_fidelity', type=float, help='fidelity of two-qubit gates')
    parser.add_argument('-mf', '--measurement_fidelity', type=float, help='fidelity of measurements')
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

    router_names = [f"router_{i}" for i in range(args.linear_size)]
    nodes = []
    for i, name in enumerate(router_names):
        config = {Topology.NAME: name,
                  Topology.TYPE: RouterNetTopo.QUANTUM_ROUTER,
                  Topology.SEED: i,
                  RouterNetTopo.MEMO_ARRAY_SIZE: args.memo_size,
                  RouterNetTopo.TEMPLATE: "router_template"}
        if args.gate_fidelity:
            config[Topology.GATE_FIDELITY] = args.gate_fidelity
        if args.measurement_fidelity:
            config[Topology.MEASUREMENT_FIDELITY] = args.measurement_fidelity
        nodes.append(config)

    bsm_names = [f"BSM_{i}_{i + 1}" for i in range(args.linear_size - 1)]
    bsm_nodes = [{Topology.NAME: bsm_name,
                  Topology.TYPE: RouterNetTopo.BSM_NODE,
                  Topology.SEED: i,
                  RouterNetTopo.TEMPLATE: "bsm_template"}
                 for i, bsm_name in enumerate(bsm_names)]

    qchannels = []
    cchannels = []
    for i, bsm_name in enumerate(bsm_names):
        qchannels.append({Topology.SRC: router_names[i],
                          Topology.DST: bsm_name,
                          Topology.DISTANCE: args.qc_length * 1000 / 2,
                          Topology.ATTENUATION: args.qc_atten})
        qchannels.append({Topology.SRC: router_names[i + 1],
                          Topology.DST: bsm_name,
                          Topology.DISTANCE: args.qc_length * 1000 / 2,
                          Topology.ATTENUATION: args.qc_atten})
        for node in [router_names[i], router_names[i + 1]]:
            cchannels.append({Topology.SRC: bsm_name,
                              Topology.DST: node,
                              Topology.DISTANCE: args.qc_length * 1000 / 2,
                              Topology.DELAY: int(args.cc_delay * MILLISECOND)})
            cchannels.append({Topology.SRC: node,
                              Topology.DST: bsm_name,
                              Topology.DISTANCE: args.qc_length * 1000 / 2,
                              Topology.DELAY: int(args.cc_delay * MILLISECOND)})

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
