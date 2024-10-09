"""Code for entanglement swapping -- for Single Heralded encoding

This module defines code for entanglement swapping.
Success is pre-determined based on network parameters.
The entanglement swapping protocol is an asymmetric protocol:

* The EntanglementSwappingA instance initiates the protocol and performs the swapping operation.
* The EntanglementSwappingB instance waits for the swapping result from EntanglementSwappingA.

The swapping results decides the following operations of EntanglementSwappingB.
Also defined in this module is the message type used by these protocols.
"""

from typing import List
from sequence.entanglement_management.entanglement_protocol import EntanglementProtocol
from sequence.topology.node import Node
from sequence.components.memory import Memory
from sequence.utils import log
from sequence.entanglement_management.swapping import SwappingMsgType, EntanglementSwappingMessage
from sequence.message import Message
from sequence.kernel.quantum_manager import BELL_DIAGONAL_STATE_FORMALISM


class ShEntanglementSwappingA(EntanglementProtocol):
    """Entanglement swapping protocol for middle router.

    The entanglement swapping protocol is an asymmetric protocol.
    EntanglementSwappingA should be instantiated on the middle node,
        where it measures a memory from each pair to be swapped.
    Results of measurement and swapping are sent to the end routers.

    Variables:
        EntanglementSwappingA.circuit (Circuit): circuit that does swapping operations.

    Attributes:
        own (Node): node that protocol instance is attached to.
        name (str): label for protocol instance.
        left_memo (Memory): a memory from one pair to be swapped.
        right_memo (Memory): a memory from the other pair to be swapped.
        left_node (str): name of node that contains memory entangling with left_memo.
        left_remote_memo (str): name of memory that entangles with left_memo.
        right_node (str): name of node that contains memory entangling with right_memo.
        right_remote_memo (str): name of memory that entangles with right_memo.
        success_prob (float): probability of a successful swapping operation.
        degradation (float): degradation factor of memory fidelity after swapping, does not apply to BDS formalism.
        is_success (bool): flag to show the result of swapping.
        left_protocol_name (str): name of left protocol.
        right_protocol_name (str): name of right protocol.
        is_twirled (bool): whether the input and output states are twirled into Werner form (default True).
    """

    def __init__(self, owner: "Node", name: str, left_memo: "Memory", right_memo: "Memory", success_prob=1,
                 degradation=0.95, is_twirled=True):
        """Constructor for entanglement swapping A protocol.

        Args:
            owner (Node): node that protocol instance is attached to.
            name (str): label for swapping protocol instance.
            left_memo (Memory): memory entangled with a memory on one distant node.
            right_memo (Memory): memory entangled with a memory on the other distant node.
            success_prob (float): probability of a successful swapping operation (default 1).
            degradation (float): degradation factor of memory fidelity after swapping (default 0.95).
                Does not apply to BDS formalism.
        """

        assert left_memo != right_memo
        EntanglementProtocol.__init__(self, owner, name)
        self.memories = [left_memo, right_memo]
        self.left_memo = left_memo
        self.right_memo = right_memo
        self.left_node = left_memo.entangled_memory['node_id']
        self.left_remote_memo = left_memo.entangled_memory['memo_id']
        self.right_node = right_memo.entangled_memory['node_id']
        self.right_remote_memo = right_memo.entangled_memory['memo_id']

        self.success_prob = success_prob
        assert 1 >= self.success_prob >= 0, "Entanglement swapping success probability must be between 0 and 1."

        self.degradation = degradation
        assert 1 >= self.degradation >= 0, "Entanglement swapping fidelity degradation factor must be between 0 and 1."

        self.is_success = False
        self.left_protocol_name = None
        self.right_protocol_name = None

        self.is_twirled = is_twirled

    def is_ready(self) -> bool:
        return self.left_protocol_name is not None and self.right_protocol_name is not None

    def set_others(self, protocol: str, node: str, memories: List[str]) -> None:
        """Method to set other entanglement protocol instance.

        Args:
            protocol (str): other protocol name.
            node (str): other node name.
            memories (List[str]): the list of memories name used on other node.
        """

        if node == self.left_memo.entangled_memory["node_id"]:
            self.left_protocol_name = protocol
        elif node == self.right_memo.entangled_memory["node_id"]:
            self.right_protocol_name = protocol
        else:
            raise Exception("Cannot pair protocol %s with %s" % (self.name, protocol))

    def start(self) -> None:
        """Method to start entanglement swapping protocol.

        Will run circuit and send measurement results to other protocols.

        Side Effects:
            Will call `update_resource_manager` method.
            Will send messages to other protocols.
        """

        log.logger.info(f"{self.owner.name} middle protocol start with ends {self.left_protocol_name}, {self.right_protocol_name}")

        assert self.left_memo.fidelity > 0 and self.right_memo.fidelity > 0
        assert self.left_memo.entangled_memory["node_id"] == self.left_node
        assert self.right_memo.entangled_memory["node_id"] == self.right_node

        if self.owner.get_generator().random() < self.success_probability():
            log.logger.debug(f'swapping successed!')
            self.is_success = True
            expire_time = min(self.left_memo.get_expire_time(), self.right_memo.get_expire_time())

            # first invoke single-memory decoherence channels on each involved quantum memory (in total 4)
            # note that bds_decohere() has changed the last_update_time to now, 
            # thus we don't need to change it for the udpated state from swapping
            self.left_memo.bds_decohere()
            self.right_memo.bds_decohere()
            left_remote_memory: Memory = self.owner.timeline.get_entity_by_name(self.left_remote_memo)
            right_remote_memory: Memory = self.owner.timeline.get_entity_by_name(self.right_remote_memo)
            left_remote_memory.bds_decohere()
            right_remote_memory.bds_decohere()

            # get BDS conditioned on success, fidelity is the first diagonal element
            new_bds = self.swapping_res()
            fidelity = new_bds[0]
            keys = [left_remote_memory.qstate_key, right_remote_memory.qstate_key]
            self.owner.timeline.quantum_manager.set(keys, new_bds)
            log.logger.debug(f'after swapping, fidelity = {fidelity:.6f}')

            msg_l = EntanglementSwappingMessage(SwappingMsgType.SWAP_RES,
                                                self.left_protocol_name,
                                                fidelity=fidelity,
                                                remote_node=self.right_memo.entangled_memory["node_id"],
                                                remote_memo=self.right_memo.entangled_memory["memo_id"],
                                                expire_time=expire_time,
                                                meas_res=[])
            msg_r = EntanglementSwappingMessage(SwappingMsgType.SWAP_RES,
                                                self.right_protocol_name,
                                                fidelity=fidelity,
                                                remote_node=self.left_memo.entangled_memory["node_id"],
                                                remote_memo=self.left_memo.entangled_memory["memo_id"],
                                                expire_time=expire_time,
                                                meas_res=[])
            
        else:
            log.logger.debug(f'swapping failed!')
            msg_l = EntanglementSwappingMessage(SwappingMsgType.SWAP_RES, self.left_protocol_name, fidelity=0)
            msg_r = EntanglementSwappingMessage(SwappingMsgType.SWAP_RES, self.right_protocol_name, fidelity=0)

        self.owner.send_message(self.left_node, msg_l)
        self.owner.send_message(self.right_node, msg_r)

        self.update_resource_manager(self.left_memo, "RAW")
        self.update_resource_manager(self.right_memo, "RAW")

    def success_probability(self) -> float:
        """A simple model for BSM success probability."""

        return self.success_prob

    def swapping_res(self) -> List[float]:
        """Method to calculate the resulting entangled state conditioned on successful swapping, for BDS formalism.

        Returns:
            List[float]: resultant bell diagonal state entries.
        """

        assert self.owner.timeline.quantum_manager.formalism == BELL_DIAGONAL_STATE_FORMALISM, \
            "Input states should be Bell diagonal states."

        left_state = self.owner.timeline.quantum_manager.get(self.left_memo.qstate_key)
        right_state = self.owner.timeline.quantum_manager.get(self.right_memo.qstate_key)

        left_elem_1, left_elem_2, left_elem_3, left_elem_4 = left_state.state  # BDS diagonal elements of left pair
        right_elem_1, right_elem_2, right_elem_3, right_elem_4 = right_state.state  # BDS diagonal elements of right pair

        if self.is_twirled:
            left_elem_2, left_elem_3, left_elem_4 = [(1-left_elem_1)/3] * 3
            right_elem_2, right_elem_3, right_elem_4 = [(1-right_elem_1)/3] * 3

        assert 1. >= left_elem_1 >= 0.5 and 1. >= right_elem_1 >= 0.5, "Input states should have fidelity above 1/2."

        # gate and measurment fidelities on swapping node, assuming two single-qubit measurements have equal fidelity
        gate_fid, meas_fid = self.owner.gate_fid, self.owner.meas_fid

        # calculate the BDS elements
        c_I = left_elem_1 * right_elem_1 + left_elem_2 * right_elem_2 + left_elem_3 * right_elem_3 + left_elem_4 * right_elem_4
        c_X = left_elem_1 * right_elem_2 + left_elem_2 * right_elem_1 + left_elem_3 * right_elem_4 + left_elem_4 * right_elem_3
        c_Y = left_elem_1 * right_elem_4 + left_elem_4 * right_elem_1 + left_elem_2 * right_elem_3 + left_elem_3 * right_elem_2
        c_Z = left_elem_1 * right_elem_3 + left_elem_3 * right_elem_1 + left_elem_2 * right_elem_4 + left_elem_4 * right_elem_2

        new_elem_1 = gate_fid * (meas_fid**2 * c_I + meas_fid*(1-meas_fid)*(c_X+c_Z) + (1-meas_fid)**2*c_Y) + (1-gate_fid)/4
        new_elem_2 = gate_fid * (meas_fid**2 * c_X + meas_fid*(1-meas_fid)*(c_I+c_Y) + (1-meas_fid)**2*c_Z) + (1-gate_fid)/4
        new_elem_3 = gate_fid * (meas_fid**2 * c_Z + meas_fid*(1-meas_fid)*(c_I+c_Y) + (1-meas_fid)**2*c_X) + (1-gate_fid)/4
        new_elem_4 = gate_fid * (meas_fid**2 * c_Y + meas_fid*(1-meas_fid)*(c_X+c_Z) + (1-meas_fid)**2*c_I) + (1-gate_fid)/4        

        if self.is_twirled:
            bds_elems = [new_elem_1, (1-new_elem_1)/3, (1-new_elem_1)/3, (1-new_elem_1)/3]
        else:
            bds_elems = [new_elem_1, new_elem_2, new_elem_3, new_elem_4]
        return bds_elems

    def received_message(self, src: str, msg: "Message") -> None:
        """Method to receive messages (should not be used on A protocol)."""

        raise Exception("EntanglementSwappingA protocol '{}' should not receive messages.".format(self.name))

    def memory_expire(self, memory: "Memory") -> None:
        """Method to receive memory expiration events.

        Releases held memories on current node.
        Memories at the remote node are released as well.

        Args:
            memory (Memory): memory that expired.

        Side Effects:
            Will invoke `update` method of attached resource manager.
            Will invoke `release_remote_protocol` or `release_remote_memory` method of resource manager.
        """

        assert self.is_ready() is False
        if self.left_protocol_name:
            self.release_remote_protocol(self.left_node)
        else:
            self.release_remote_memory(self.left_node, self.left_remote_memo)
        if self.right_protocol_name:
            self.release_remote_protocol(self.right_node)
        else:
            self.release_remote_memory(self.right_node, self.right_remote_memo)

        for memo in self.memories:
            if memo == memory:
                self.update_resource_manager(memo, "RAW")
            else:
                self.update_resource_manager(memo, "ENTANGLED")

    def release_remote_protocol(self, remote_node: str):
        self.owner.resource_manager.release_remote_protocol(remote_node, self)

    def release_remote_memory(self, remote_node: str, remote_memo: str):
        self.owner.resource_manager.release_remote_memory(remote_node, remote_memo)


class ShEntanglementSwappingB(EntanglementProtocol):
    """Entanglement swapping protocol for middle router.

    The entanglement swapping protocol is an asymmetric protocol.
    EntanglementSwappingB should be instantiated on the end nodes, where it waits for swapping results from the middle node.

    Variables:
        EntanglementSwappingB.x_cir (Circuit): circuit that corrects state with an x gate.
        EntanglementSwappingB.z_cir (Circuit): circuit that corrects state with z gate.
        EntanglementSwappingB.x_z_cir (Circuit): circuit that corrects state with an x and z gate.

    Attributes:
        own (QuantumRouter): node that protocol instance is attached to.
        name (str): name of protocol instance.
        memory (Memory): memory to swap.
        remote_protocol_name (str): name of another protocol to communicate with for swapping.
        remote_node_name (str): name of node hosting the other protocol.
    """

    def __init__(self, own: "Node", name: str, hold_memo: "Memory"):
        """Constructor for entanglement swapping B protocol.

        Args:
            own (Node): node protocol instance is attached to.
            name (str): name of protocol instance.
            hold_memo (Memory): memory entangled with a memory on middle node.
        """

        EntanglementProtocol.__init__(self, own, name)

        self.memories = [hold_memo]
        self.memory = hold_memo
        self.remote_protocol_name = None
        self.remote_node_name = None


    def is_ready(self) -> bool:
        return self.remote_protocol_name is not None

    def set_others(self, protocol: str, node: str, memories: List[str]) -> None:
        """Method to set other entanglement protocol instance.

        Args:
            protocol (str): other protocol name.
            node (str): other node name.
            memories (List[str]): the list of memory names used on other node.
        """
        self.remote_node_name = node
        self.remote_protocol_name = protocol

    def received_message(self, src: str, msg: "EntanglementSwappingMessage") -> None:
        """Method to receive messages from EntanglementSwappingA.

        Args:
            src (str): name of node sending message.
            msg (EntanglementSwappingMesssage): message sent.

        Side Effects:
            Will invoke `update_resource_manager` method.
        """

        log.logger.debug(self.owner.name + " protocol received_message from node {}, fidelity={}".format(src, msg.fidelity))

        assert src == self.remote_node_name

        if msg.fidelity > 0 and self.owner.timeline.now() < msg.expire_time:
            # if using BDS formalism,
            # updated BDS has been determined analytically taking into account local correction,
            # thus need to do nothing
            pass

            self.memory.fidelity = msg.fidelity
            self.memory.entangled_memory["node_id"] = msg.remote_node
            self.memory.entangled_memory["memo_id"] = msg.remote_memo
            self.memory.update_expire_time(msg.expire_time)
            # TODO: if time-dependent decoherence exists,
            #  the current state should have undergone decoherence during classical communication
            self.update_resource_manager(self.memory, "ENTANGLED")
        else:
            self.update_resource_manager(self.memory, "RAW")

    def start(self) -> None:
        log.logger.info(f"{self.owner.name} end protocol start with partner {self.remote_node_name}")

    def memory_expire(self, memory: "Memory") -> None:
        """Method to deal with expired memories.

        Args:
            memory (Memory): memory that expired.

        Side Effects:
            Will update memory in attached resource manager.
        """

        self.update_resource_manager(self.memory, "RAW")

    def release(self) -> None:
        self.update_resource_manager(self.memory, "ENTANGLED")
