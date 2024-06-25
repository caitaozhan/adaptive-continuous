'''Definition of Reservation protocol for the adaptive-continuous protocol
'''

from typing import TYPE_CHECKING, List
from sequence.network_management.reservation import ResourceReservationProtocol, Reservation
from sequence.resource_management.rule_manager import Rule
from sequence.network_management.reservation import eg_rule_action1, eg_rule_action2, eg_rule_condition
from sequence.kernel.event import Event
from sequence.kernel.process import Process

if TYPE_CHECKING:
    from node import QuantumRouterAdaptive


class ResourceReservationProtocolAdaptive(ResourceReservationProtocol):
    '''ReservationProtocol for node resources customized for adaptive-continuous protocol
    Task:
        update the cache
    '''

    def __init__(self, owner: "QuantumRouterAdaptive", name: str, memory_array_name: str):
        super().__init__(owner, name, memory_array_name)


    def create_rules(self, path: list, reservation: Reservation) -> List["Rule"]:
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


    def load_rules(self, rules: List['Rule'], reservation: Reservation):
        """Method to add created rules to resource manager.

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


