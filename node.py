''' the quantum router for adaptive-continuous protocol
'''

from sequence.topology.node import QuantumRouter
from sequence.resource_management.resource_manager import ResourceManager
from sequence.network_management.routing import StaticRoutingProtocol
from sequence.kernel.timeline import Timeline
from sequence.network_management.network_manager import NetworkManager
from reservation import ResourceReservationProtocolAdaptive
from adaptive_continuous import AdaptiveContinuousProtocol


class QuantumRouterAdaptive(QuantumRouter):
    '''The quantum router customized for the adaptive continuous protocol
    Newly added attributes:
        1) cache (list): storing the routing path
        2) Adaptive Protocol
    '''
    def __init__(self, name: str, tl: Timeline, memo_size: int = 50, seed: int = None, component_templates: dict = None):
        super().__init__(name, tl, memo_size, seed, component_templates)
        self.cache = [] # each item is (timestamp: int, path: list)
        self.adaptive_continuous = AdaptiveContinuousProtocol(self, f'{self.name}.adaptive_continuous')

    def init_managers(self, memo_arr_name: str):
        '''override QuantumRouter.init_manager()
           init the resource mansger and network manager
        Args:
            memo_arr_name: the name of the memory array
        '''
        # setup resource manager
        resource_manager = ResourceManager(self, memo_arr_name)
        self.set_resource_manager(resource_manager)

        # setup network manager
        swapping_success_rate = 0.5
        network_manager = NetworkManager(self, [])
        routing_protocol = StaticRoutingProtocol(self, f'{self.name}.StaticRoutingProtocol', {})
        rsvp_protocol = ResourceReservationProtocolAdaptive(self, f'{self.name}.RSVP', memo_arr_name)
        rsvp_protocol.set_swapping_success_rate(swapping_success_rate)
        routing_protocol.upper_protocols.append(rsvp_protocol)
        rsvp_protocol.lower_protocols.append(routing_protocol)
        network_manager.load_stack([routing_protocol, rsvp_protocol])
        self.set_network_manager(network_manager)
