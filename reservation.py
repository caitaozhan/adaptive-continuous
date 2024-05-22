'''Definition of Reservation protocol for the adaptive-continuous protocol
'''

from typing import TYPE_CHECKING
from sequence.network_management.reservation import ResourceReservationProtocol

if TYPE_CHECKING:
    from node import QuantumRouterAdaptive


class ResourceReservationProtocolAdaptive(ResourceReservationProtocol):
    '''ReservationProtocol for node resources customized for adaptive-continuous protocol
    '''
    def __init__(self, owner: "QuantumRouterAdaptive", name: str, memory_array_name: str):
        super().__init__(owner, name, memory_array_name)

