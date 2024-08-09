'''The Rule class customized for the adaptive continuous protocol
'''

from typing import List, TYPE_CHECKING
from sequence.utils import log
from sequence.resource_management.rule_manager import Rule, RuleManager, ActionFunc, ConditionFunc, Arguments
from sequence.resource_management.memory_manager import MemoryInfo
from sequence.entanglement_management.generation import EntanglementGenerationA

from swap_memory import SwapMemoryProtocol, swapmem_rule_action1, swapmem_rule_action2

if TYPE_CHECKING:
    from adaptive_continuous import AdaptiveContinuousProtocol


class RuleAdaptive(Rule):
    """Definition of rule for the rule manager customized for the Adaptive continuous protocol.

    Rule objects are installed on and interacted with by the rule manager.

    Note: (7/4/2024) Only used to create entanglement generation protocols when processing the requests

    Attributes:
        priority (int): priority of the rule, used as a tiebreaker when conditions of multiple rules are met.
        action (Callable[[List["MemoryInfo"]], Tuple["Protocol", List["str"], List[Callable[["Protocol"], bool]]]]):
            action to take when rule condition is met.
        condition (Callable[["MemoryInfo", "MemoryManager"], List["MemoryInfo"]]): condition required by rule.
        protocols (List[Protocols]): protocols created by rule.
        rule_manager (RuleManager): reference to rule manager object where rule is installed.
        reservation (Reservation): associated reservation.
    """

    def __init__(self, priority: int, action: ActionFunc, condition: ConditionFunc, action_args: Arguments, condition_args: Arguments):
        super().__init__(priority, action, condition, action_args, condition_args)

    def do(self, memories_info: List["MemoryInfo"]) -> None:
        """Method to perform rule activation and send requirements to other nodes.

           Note: check before executing EG protocols

        Args:
            memories_info (List[MemoryInfo]): list of memory infos for memories meeting requirements.
        """
        protocol, req_dsts, req_condition_funcs, req_args = self.action(memories_info, self.action_args)
        log.logger.info('{} rule generates protocol {}'.format(self.rule_manager, protocol.name))

        # check if adaptive_continuous's generated_entanglement_links can be used -- to reduce time to service
        if isinstance(protocol, EntanglementGenerationA):
            this_node_name = self.get_this_node_name()
            remote_node_name = protocol.remote_node_name
            adaptive_continuous = self.get_adaptive_continuous_protocol()
            matched_entanglement_pair = adaptive_continuous.match_generated_entanglement_pair(this_node_name, remote_node_name)
            if matched_entanglement_pair is not None:  # there exists an pre-generated entanglement pair
                if len(req_dsts) == 1 and req_dsts[0] is None:
                    # this node decides the entanglement pair
                    adaptive_continuous.remove_entanglement_pair(matched_entanglement_pair)
                    self.action_args['entanglement_pair'] = matched_entanglement_pair
                    protocol, req_dsts, req_condition_funcs, req_args = swapmem_rule_action1(memories_info, self.action_args)
                    log.logger.info(f'{this_node_name} generates protocol {protocol.name} and replace EGA; matched entanglement pair {matched_entanglement_pair}')
                else:
                    # this node send the request for pairing (resource manager)
                    protocol, req_dsts, req_condition_funcs, req_args = swapmem_rule_action2(memories_info, self.action_args)
                    log.logger.info(f'{this_node_name} generates protocol {protocol.name} and replace EGA; let {remote_node_name} decide the matched entanglement pair')
                   
        protocol.rule = self
        self.protocols.append(protocol)
        for info in memories_info:
            info.memory.detach(info.memory.memory_array)
            info.memory.attach(protocol)
        for dst, req_func, args in zip(req_dsts, req_condition_funcs, req_args):
            self.rule_manager.send_request(protocol, dst, req_func, args)

    def get_this_node_name(self) -> str:
        return self.rule_manager.resource_manager.owner.name

    def get_adaptive_continuous_protocol(self) -> "AdaptiveContinuousProtocol":
        return self.rule_manager.resource_manager.owner.adaptive_continuous



class RuleManagerAdaptive(RuleManager):
    """Class to manage and follow installed rules.

    The RuleManager checks available rules when the state of a memory is updated.
    Rules that are met have their action executed by the rule manager.

    Attributes:
        rules (List[Rules]): List of installed rules.
        resource_manager (ResourceManager): reference to the resource manager using this rule manager.
    """

    def __init__(self):
        """Constructor for rule manager class."""
        super().__init__()

    def send_request_swap_memory(self, req_dst, entanglement_pair):
        # log.logger.info('{} Rule Manager send request for protocol {} to {}'.format(self.resource_manager.owner, protocol.name, req_dst))
        return self.resource_manager.send_request_swap_memory()
