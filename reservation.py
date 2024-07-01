'''Definition of Reservation protocol for the adaptive-continuous protocol
'''

from typing import TYPE_CHECKING, List
from sequence.network_management.reservation import ResourceReservationProtocol, Reservation, ResourceReservationMessage, QCap, RSVPMsgType
from sequence.resource_management.rule_manager import Rule
from sequence.network_management.reservation import eg_rule_action1, eg_rule_action2, eg_rule_condition
from sequence.kernel.event import Event
from sequence.kernel.process import Process

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
    Task:
        update the cache
    '''

    def __init__(self, owner: "QuantumRouterAdaptive", name: str, memory_array_name: str):
        super().__init__(owner, name, memory_array_name)


    def create_rules_adaptive(self, path: list, reservation: ReservationAdaptive) -> List["Rule"]:
        """Method to create rules for entanglement generation for a successful AC protocol's request.

        Rules are used to direct the flow of information/entanglement in the resource manager.

        Args:
            path (List[str]): list of node names in entanglement path.
            reservation (Reservation): approved reservation.

        Returns:
            List[Rule]: list of rules created by the method.
        """
        rules = []
        memory_indices = []
        for card in self.timecards:
            if reservation in card.reservations:
                memory_indices.append(card.memory_index)

        index = path.index(self.owner.name)  # the location of this node along the path from initiator to responder

        # create rules for entanglement generation
        if index > 0:
            condition_args = {"memory_indices": memory_indices[:reservation.memory_size]}
            action_args = {"mid": self.owner.map_to_middle_node[path[index - 1]], "path": path, "index": index}
            rule = Rule(10, eg_rule_action1, eg_rule_condition, action_args, condition_args)
            rules.append(rule)

        if index < len(path) - 1:
            if index == 0:
                condition_args = {"memory_indices": memory_indices[:reservation.memory_size]}
            else:
                condition_args = {"memory_indices": memory_indices[reservation.memory_size:]}

            action_args = {"mid": self.owner.map_to_middle_node[path[index + 1]],
                           "path": path, "index": index, "name": self.owner.name, "reservation": reservation}
            rule = Rule(10, eg_rule_action2, eg_rule_condition, action_args, condition_args)
            rules.append(rule)

        for rule in rules:
            rule.set_reservation(reservation)
        
        return rules


    def load_rules_adaptive(self, rules: List['Rule'], reservation: ReservationAdaptive):
        """Method to add AC protocol created rules to resource manager.

        This method will schedule the resource manager to load all rules at the reservation start time.
        The rules will be set to expire at the reservation end time.

        Args:
            rules (List[Rules]): rules to add.
            reservation (Reservation): reservation that created the rules.
        """

        self.accepted_reservation.append(reservation)
        for card in self.timecards:
            if reservation in card.reservations:
                process = Process(self.owner.resource_manager, "update", [None, self.memo_arr[card.memory_index], "RAW"])
                event = Event(reservation.end_time, process, 1)
                self.owner.timeline.schedule(event)

                process = Process(self.owner.adaptive_continuous, "adaptive_memory_used_minus_one", [])
                event = Event(reservation.end_time, process, 2)
                self.owner.timeline.schedule(event)

        for rule in rules:
            process = Process(self.owner.resource_manager, "load", [rule])
            event = Event(reservation.start_time, process)
            self.owner.timeline.schedule(event)

            process = Process(self.owner.resource_manager, "expire", [rule])
            event = Event(reservation.end_time, process, 0)
            self.owner.timeline.schedule(event)


