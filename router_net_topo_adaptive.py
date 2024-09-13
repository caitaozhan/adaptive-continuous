'''Generate quantum network with quantum routers customized for the adaptive-continuous protocol
'''

from networkx import Graph, dijkstra_path, exception
import random

from sequence.topology.topology import Topology as Topo
from sequence.topology.router_net_topo import RouterNetTopo
from sequence.kernel.timeline import Timeline


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
            template = self.templates.get(template_name, {})

            if node_type == self.BSM_NODE:
                others = self.bsm_to_router_map[name]
                node_obj = BSMNodeAdaptive(name, self.tl, others, component_templates=template)
            elif node_type == self.QUANTUM_ROUTER:
                memo_size = node.get(self.MEMO_ARRAY_SIZE, 0)
                node_obj = QuantumRouterAdaptive(name, self.tl, memo_size, component_templates=template)
            else:
                raise ValueError("Unknown type of node '{}'".format(node_type))

            node_obj.set_seed(seed)
            self.nodes[node_type].append(node_obj)


    def _generate_forwarding_table(self, config: dict):
        """For static routing."""
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
                router, bsm = qc.sender.name, qc.receiver
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
                        path = dijkstra_path(graph, src.name, dst_name)
                    else:
                        path = dijkstra_path(graph, dst_name, src.name)[::-1]
                    next_hop = path[1]
                    # routing protocol locates at the bottom of the stack
                    routing_protocol = src.network_manager.protocol_stack[0]  # guarantee that [0] is the routing protocol?
                    routing_protocol.add_forwarding_rule(dst_name, next_hop)
                except exception.NetworkXNoPath:
                    pass

    def update_stop_time(self, stop_time: int) -> None:
        """Update the stop time

        Args:
            stop_time (int): time in picoseconds
        """
        self.tl.stop_time = stop_time
