"""Definition of the Network Manager customized for the 
"""

from sequence.topology.node import QuantumRouter
from sequence.protocol import StackProtocol
from sequence.network_management.network_manager import NetworkManager

from adaptive_continuous import AdaptiveContinuousProtocol
from typing import List

class NetworkManagerAdaptive(NetworkManager):
    '''Network manager for the Adaptive, Continuous Protocol
    
    Newly added:
        1) cache (dict): storing the routing path
        2) Adaptive Protocol
    '''

    def __init__(self, owner: QuantumRouter, protocol_stack: List[StackProtocol]):
        """Constructor for network manager.

        Args:
            owner (QuantumRouter): node network manager is attached to.
            protocol_stack (List[StackProtocol]): stack of protocols to use for processing.
        """
        super().__init__(owner, protocol_stack)
        self.path_cache = [] # each item is (timestamp: int, path: list)
        self.adaptive_continuous = AdaptiveContinuousProtocol()
