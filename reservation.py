'''Definition of Reservation protocol for the adaptive-continuous protocol
'''

from typing import TYPE_CHECKING, List, Tuple, Dict, Any
from sequence.network_management.reservation import Reservation
from sequence.network_management.rsvp import RSVPMsgType, RSVPProtocol as ResourceReservationProtocol,RSVPMessage as ResourceReservationMessage, QCap
from sequence.resource_management.rule_manager import Rule
# from sequence.network_management.reservation import 
from sequence.kernel.event import Event
from sequence.kernel.process import Process
from sequence.resource_management.memory_manager import MemoryInfo
from sequence.resource_management.rule_manager import Arguments
from sequence.entanglement_management.entanglement_protocol import EntanglementProtocol

from purification import BBPSSW_bds

if TYPE_CHECKING:
    from node import QuantumRouterAdaptive

class ReservationAdaptive(Reservation):
    """Tracking of reservation parameters for the network manager.
       Each request will generate a reservation

       Note: the only difference compared with the parant class is a minor change in __str__()
       
    Attributes:
        initiator (str): name of the node that created the reservation request.
        responder (str): name of distant node with witch entanglement is requested.
        start_time (int): simulation time at which entanglement should be attempted.
        end_time (int): simulation time at which resources may be released.
        memory_size (int): number of entangled memory pairs requested.
        path (list): a list of router names from the source to destination
    """

    def __init__(self, initiator: str, responder: str, start_time: int,
                 end_time: int, memory_size: int, fidelity: float):
        """Constructor for the reservation class.

        Args:
            initiator (str): node initiating the request.
            responder (str): node with which entanglement is requested.
            start_time (int): simulation start time of entanglement.
            end_time (int): simulation end time of entanglement.
            memory_size (int): number of entangled memories requested.
            fidelity (float): desired fidelity of entanglement.
        """
        super().__init__(initiator, responder, start_time, end_time, memory_size, fidelity)

    def __str__(self) -> str:
        return "|AdaptiveContinuous; initiator={}; responder={}; start_time={:,}; end_time={:,}; memory_size={}; target_fidelity={}|".format(
                self.initiator, self.responder, int(self.start_time), int(self.end_time), self.memory_size, self.fidelity)

    def __repr__(self) -> str:
        return self.__str__()



class ResourceReservationProtocolAdaptive(ResourceReservationProtocol):
    '''ReservationProtocol for node resources customized for adaptive-continuous protocol
    '''

    def __init__(self, owner: "QuantumRouterAdaptive", name: str, memory_array_name: str):
        super().__init__(owner, name, memory_array_name)


    def pop(self, src: str, msg: "ResourceReservationMessage"):
        """Method to receive messages from lower protocols.

        Messages may be of 3 types, causing different network manager behavior:

        1. REQUEST: requests are evaluated, and forwarded along the path if accepted. Otherwise a REJECT message is sent back.
        2. REJECT: any reserved resources are released and the message forwarded back towards the initializer.
        3. APPROVE: rules are created to achieve the approved request. The message is forwarded back towards the initializer.

        Args:
            src (str): source node of the message.
            msg (ResourceReservationMessage): message received.
        
        Side Effects:
            May push/pop to lower/upper attached protocols (or network manager).

        Assumption:
            the path initiator -> responder is same as the reverse path
        """

        if msg.msg_type == RSVPMsgType.REQUEST:
            assert self.owner.timeline.now() < msg.reservation.start_time
            qcap = QCap(self.owner.name)
            msg.qcaps.append(qcap)
            path = [qcap.node for qcap in msg.qcaps]
            if self.schedule(msg.reservation):   # schedule success
                if self.owner.name == msg.reservation.responder: # this node is the responder
                    self.accepted_reservations.append(msg.reservation)
                    msg.reservation.set_path(path)
                    new_msg = ResourceReservationMessage(RSVPMsgType.APPROVE, self.name, msg.reservation, path=path)
                    self._pop(msg=new_msg)
                    self._push(dst=None, msg=new_msg, next_hop=src)
                else:                                            # this node is an intermediate node (not responder)
                    self._push(dst=msg.reservation.responder, msg=msg)
            else:                                # schedule failed
                new_msg = ResourceReservationMessage(RSVPMsgType.REJECT, self.name, msg.reservation, path=path)
                self._push(dst=None, msg=new_msg, next_hop=src)
        elif msg.msg_type == RSVPMsgType.REJECT:
            for card in self.timecards:
                card.remove(msg.reservation)
            if msg.reservation.initiator == self.owner.name:
                self._pop(msg=msg)
            else:
                next_hop = self.next_hop_when_tracing_back(msg.path)
                self._push(dst=None, msg=msg, next_hop=next_hop)
        elif msg.msg_type == RSVPMsgType.APPROVE:
            self.accepted_reservations.append(msg.reservation)
            self._pop(msg=msg)
            if msg.reservation.initiator != self.owner.name:
                next_hop = self.next_hop_when_tracing_back(msg.path)
                self._push(dst=None, msg=msg, next_hop=next_hop)
        else:
            raise Exception("Unknown type of message", msg.msg_type)

    def next_hop_when_tracing_back(self, path: List[str]) -> str:
        '''the next hop when going back from the responder to the initiator

        Args:
            path (List[str]): a list of router names that goes from initiator to responder
        Return:
            str: the name of the next hop
        '''
        cur_index = path.index(self.owner.name)
        assert cur_index >= 1, f'{cur_index} must be larger equal than 1'
        next_hop = path[cur_index - 1]
        return next_hop
