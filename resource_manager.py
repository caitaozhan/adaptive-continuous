"""The Resource Manager customized for the adaptive continuous protocol
"""

from typing import TYPE_CHECKING, Optional
from enum import auto, Enum

from sequence.resource_management.resource_manager import ResourceManager, ResourceManagerMessage, ResourceManagerMsgType
from sequence.entanglement_management.entanglement_protocol import EntanglementProtocol
from sequence.components.memory import Memory
from sequence.resource_management.memory_manager import MemoryInfo
from sequence.entanglement_management.generation import EntanglementGenerationA
from sequence.utils import log

from memory_manager import MemoryManagerAdaptive
from rule_manager import RuleManagerAdaptive, Arguments
from reservation import ReservationAdaptive
from adaptive_continuous import AdaptiveContinuousProtocol


if TYPE_CHECKING:
    from node import QuantumRouterAdaptive


class ResourceManagerAdaptive(ResourceManager):
    """Class to define the resource manager.

    Note: needs to keep track which entanglement pairs are generated via the Adaptive Continuous protocol

    The resource manager uses a memory manager to track memory states for the entanglement protocols.
    It also uses a rule manager to direct the creation and operation of entanglement protocols.

    Attributes:
        name (str): label for manager instance.
        owner (QuantumRouter): node that resource manager is attached to.
        memory_manager (MemoryManager): internal memory manager object.
        rule_manager (RuleManager): internal rule manager object.
        pending_protocols (List[Protocol]): list of protocols awaiting a response for a remote resource request.
        waiting_protocols (List[Protocol]): list of protocols awaiting a request from a remote protocol.
    """

    def __init__(self, owner: "QuantumRouterAdaptive", memory_array_name: str):
        super().__init__(owner, memory_array_name)
        self.rule_manager = RuleManagerAdaptive()    # reassign the rule manager
        self.rule_manager.set_resource_manager(self)
        self.memory_manager = MemoryManagerAdaptive(owner.components[memory_array_name])
        self.memory_manager.set_resource_manager(self)

    def update(self, protocol: "EntanglementProtocol", memory: "Memory", state: str) -> None:
        """Method to update state of memory after completion of entanglement management protocol.

        Args:
            protocol (EntanglementProtocol): concerned protocol. If not None, then remove it from everywhere
            memory (Memory): memory to update.
            state (str): new state for the memory.

        Side Effects:
            May modify memory state, and modify any attached protocols.
            May add generated entanglement pair into the adaptive_continuous
        """

        self.memory_manager.update(memory, state)

        if protocol:
            memory.detach(protocol)
            memory.attach(memory.memory_array)
            if protocol in protocol.rule.protocols:
                protocol.rule.protocols.remove(protocol)

            # let the AC protocol track this entanglement link
            if isinstance(protocol, EntanglementGenerationA) and state == MemoryInfo.ENTANGLED: # entanglement succeed
                if isinstance(protocol.rule.reservation, ReservationAdaptive): # Adaptive Continuous Protocol's reservation
                    adaptive_continuous = self.get_adaptive_continuous_protocol()
                    entanglment_pair = ((self.owner.name, memory.name), (memory.entangled_memory['node_id'], memory.entangled_memory['memo_id']))
                    adaptive_continuous.add_generated_entanglement_pair(entanglment_pair)

        if protocol in self.owner.protocols:
            self.owner.protocols.remove(protocol)

        if protocol in self.waiting_protocols:
            self.waiting_protocols.remove(protocol)

        if protocol in self.pending_protocols:
            self.pending_protocols.remove(protocol)

        # check if any rules have been met
        memo_info = self.memory_manager.get_info_by_memory(memory)
        for rule in self.rule_manager:
            memories_info = rule.is_valid(memo_info)
            if len(memories_info) > 0:
                rule.do(memories_info)
                for info in memories_info:
                    info.to_occupied()
                return

        self.owner.get_idle_memory(memo_info)


    def update_swap_memory(self, protocol: "EntanglementProtocol", memory: "Memory", state: str) -> None:
        """Method to update state of memory after completion of entanglement management protocol.

        Compared with update(), the update_swap_memory() don't have the self.memory_manager.update() in the first line
        Also, don't need to inform the AC protocol

        Args:
            protocol (EntanglementProtocol): concerned protocol. If not None, then remove it from everywhere
            memory (Memory): memory to update.
            state (str): new state for the memory. NOTE: not used

        Side Effects:
            May modify memory state, and modify any attached protocols.
            May add generated entanglement pair into the adaptive_continuous
        """

        if protocol:
            memory.detach(protocol)
            memory.attach(memory.memory_array)
            if protocol in protocol.rule.protocols:
                protocol.rule.protocols.remove(protocol)

        if protocol in self.owner.protocols:
            self.owner.protocols.remove(protocol)

        if protocol in self.waiting_protocols:
            self.waiting_protocols.remove(protocol)

        if protocol in self.pending_protocols:
            self.pending_protocols.remove(protocol)

        # check if any rules have been met
        memo_info = self.memory_manager.get_info_by_memory(memory)
        for rule in self.rule_manager:
            memories_info = rule.is_valid(memo_info)
            if len(memories_info) > 0:
                rule.do(memories_info)
                for info in memories_info:
                    info.to_occupied()
                return

        self.owner.get_idle_memory(memo_info)


    def get_adaptive_continuous_protocol(self) -> AdaptiveContinuousProtocol:
        '''return the adaptive continuous protocol
        '''
        return self.owner.adaptive_continuous


    def swap_two_memory(self, occupied_memory_name: str, entangled_memory_name: str):
        '''swap two quantum memories
        '''
        self.memory_manager.swap_two_memory(occupied_memory_name, entangled_memory_name)


    def check_entangled_memory(self, entangled_memory_name: str) -> bool:
        '''return True if the memory by parameter entangled_memory_name is indeed entangled, otherwise False
        '''
        return self.memory_manager.check_entangled_memory(entangled_memory_name)
