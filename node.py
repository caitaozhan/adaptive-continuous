''' the quantum router for adaptive-continuous protocol
'''

from sequence.topology.node import QuantumRouter
from sequence.resource_management.resource_manager import ResourceManager
from sequence.network_management.routing import StaticRoutingProtocol
from sequence.kernel.timeline import Timeline
from network_manager import NetworkManagerAdaptive
from reservation import ResourceReservationProtocolAdaptive


class QuantumRouterAdaptive(QuantumRouter):
    '''The adaptive 
    '''
    def __init__(self, name: str, tl: Timeline, memo_size: int = 50, seed: int = None, component_templates: dict = None):
        super().__init__(name, tl, memo_size, seed, component_templates)
        memo_arr_name = name + ".MemoryArray"
        self.init_managers(memo_arr_name)

    def init_managers(self, memo_arr_name: str):
        '''init the resource mansger and network manager
        Args:
            memo_arr_name: the name of the memory array
        '''
        # setup resource manager
        self.resource_manager = None
        resource_manager = ResourceManager(self, memo_arr_name)
        self.set_resource_manager(resource_manager)

        # setup network manager
        swapping_success_rate = 0.5
        network_manager = NetworkManagerAdaptive(self, [])
        self.network_manager = None
        routing_protocol = StaticRoutingProtocol(self, f'{self.name}.StaticRoutingProtocol', {})
        rsvp_protocol = ResourceReservationProtocolAdaptive(self, f'{self.name}.RSVP', memo_arr_name)
        rsvp_protocol.set_swapping_success_rate(swapping_success_rate)
        routing_protocol.upper_protocols.append(rsvp_protocol)
        rsvp_protocol.lower_protocols.append(routing_protocol)
        network_manager.load_stack([routing_protocol, rsvp_protocol])
        self.set_network_manager(network_manager)
