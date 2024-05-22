'''Generate quantum network with quantum routers customized for the adaptive-continuous protocol
'''

from sequence.topology.topology import Topology as Topo
from sequence.topology.node import BSMNode
from sequence.topology.router_net_topo import RouterNetTopo

from node import QuantumRouterAdaptive


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
                node_obj = BSMNode(name, self.tl, others, component_templates=template)
            elif node_type == self.QUANTUM_ROUTER:
                memo_size = node.get(self.MEMO_ARRAY_SIZE, 0)
                node_obj = QuantumRouterAdaptive(name, self.tl, memo_size, component_templates=template)
            else:
                raise ValueError("Unknown type of node '{}'".format(node_type))

            node_obj.set_seed(seed)
            self.nodes[node_type].append(node_obj)
