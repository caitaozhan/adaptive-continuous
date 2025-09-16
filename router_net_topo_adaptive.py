'''Generate quantum network with quantum routers customized for the adaptive-continuous protocol
'''

from networkx import Graph, single_source_dijkstra, exception
from sequence.topology.topology import Topology as Topo
from sequence.topology.router_net_topo import RouterNetTopo
from sequence.kernel.timeline import Timeline
from sequence.kernel.quantum_manager import BELL_DIAGONAL_STATE_FORMALISM
from sequence.constants import SPEED_OF_LIGHT, MICROSECOND

from node import QuantumRouterAdaptive, BSMNodeAdaptive


class RouterNetTopoAdaptive(RouterNetTopo):
    '''Class for generating quantum network with quantum routers customized for the adaptive-continuous protocol
    '''

    def __init__(self, conf_file_name: str):
        super().__init__(conf_file_name)

    def _add_nodes(self, config: dict):
        '''overrides RouterNetTopo._add_nodes()
        '''
        for node in config[Topo.ALL_NODE]:
            seed = node[Topo.SEED]
            node_type = node[Topo.TYPE]
            name = node[Topo.NAME]
            template_name = node.get(Topo.TEMPLATE, None)
            component_templates = self.templates.get(template_name, {})
            if self.encoding_type is None:
                self.encoding_type = component_templates.get('encoding_type', 'single_atom')

            if node_type == self.BSM_NODE:
                others = self.bsm_to_router_map[name]
                seed = node.get(self.SEED, 0)
                node_obj = BSMNodeAdaptive(name, self.tl, others, seed, component_templates)
            elif node_type == self.QUANTUM_ROUTER:
                memo_size = node.get(self.MEMO_ARRAY_SIZE, 0)
                seed = node.get(self.SEED, 0)
                gate_fidelity = node.get(self.GATE_FIDELITY, 1)
                measurement_fidelity = node.get(self.MEASUREMENT_FIDELITY, 1)
                node_obj = QuantumRouterAdaptive(name, self.tl, memo_size, seed, component_templates, gate_fidelity, measurement_fidelity)
            else:
                raise ValueError("Unknown type of node '{}'".format(node_type))

            node_obj.set_seed(seed)
            self.nodes[node_type].append(node_obj)

        if self.encoding_type == "single_heralded":
            self.tl.quantum_manager.set_global_manager_formalism(BELL_DIAGONAL_STATE_FORMALISM)


    def _generate_forwarding_table(self, config: dict):
        """For static routing.
           Also updating the classical communication delay

        Args:
            config (dict): the config file
        """

        all_paths = {}  # (src, dst) -> (length: float, hop: int, path: tuple)

        graph = Graph()
        for node in config[Topo.ALL_NODE]:
            if node[Topo.TYPE] == self.QUANTUM_ROUTER:
                graph.add_node(node[Topo.NAME])

        costs = {}
        if config[self.IS_PARALLEL]:
            for qc in config[self.ALL_Q_CHANNEL]:
                router, bsm = qc[self.SRC], qc[self.DST]
                if bsm not in costs:
                    costs[bsm] = [router, qc[self.DISTANCE]]
                else:
                    costs[bsm] = [router] + costs[bsm]
                    costs[bsm][-1] += qc[self.DISTANCE]
        else:
            for qc in self.qchannels:
                # update all_paths
                router, bsm = qc.sender.name, qc.receiver
                all_paths[(router, bsm)] = (qc.distance, 0, (router, bsm))
                all_paths[(bsm, router)] = (qc.distance, 0, (bsm, router))

                if bsm not in costs:
                    costs[bsm] = [router, qc.distance]
                else:
                    costs[bsm] = [router] + costs[bsm]
                    costs[bsm][-1] += qc.distance


        graph.add_weighted_edges_from(costs.values())
        for src in self.nodes[self.QUANTUM_ROUTER]:
            for dst_name in graph.nodes:
                if src.name == dst_name:
                    continue
                try:
                    if dst_name > src.name:
                        length, path = single_source_dijkstra(graph, src.name, dst_name)
                    else:
                        length, path = single_source_dijkstra(graph, dst_name, src.name)
                        path = path[::-1]
                    # update all_paths
                    hop_count = len(path) - 2
                    all_paths[(src.name, dst_name)] = (length, hop_count, tuple(path))
                    
                    next_hop = path[1]
                    # routing protocol locates at the bottom of the stack
                    routing_protocol = src.network_manager.protocol_stack[0]  # guarantee that [0] is the routing protocol?
                    routing_protocol.add_forwarding_rule(dst_name, next_hop)
                except exception.NetworkXNoPath:
                    pass
        
        # update the classical delay and the distance
        def classical_delay(distance: float, hop_count: int) -> float:
            """Model the classical delay as a function of distance and hop count
            """
            return distance / SPEED_OF_LIGHT + hop_count * 20 * MICROSECOND + 100 * MICROSECOND

        for cc in self.cchannels:
            src = cc.sender.name
            dst = cc.receiver
            length, hop_count, path = all_paths[(src, dst)]
            cc.delay = classical_delay(length, hop_count)
            cc.distance = length   # not important
            # print(f'{path}: {cc.delay/1e6}us')

    def update_stop_time(self, stop_time: int) -> None:
        """Update the stop time

        Args:
            stop_time (int): time in picoseconds
        """
        self.tl.stop_time = stop_time
