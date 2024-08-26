'''a modified version of entanglement swapping protocol
'''

from sequence.entanglement_management.swapping import EntanglementSwappingA, SwappingMsgType, EntanglementSwappingMessage
from sequence.topology.node import Node
from sequence.components.memory import Memory
from sequence.utils import log
from sequence.kernel.event import Event
from sequence.kernel.process import Process
from sequence.resource_management.memory_manager import MemoryInfo



class EtanglementSwappingAdelay(EntanglementSwappingA):
    '''only change is in start() method, where the update memory to "RAW" is delayed
    '''

    def __init__(self, owner: "Node", name: str, left_memo: "Memory", right_memo: "Memory", success_prob=1, degradation=0.95):
        """Constructor for entanglement swapping A protocol.

        Args:
            owner (Node): node that protocol instance is attached to.
            name (str): label for swapping protocol instance.
            left_memo (Memory): memory entangled with a memory on one distant node.
            right_memo (Memory): memory entangled with a memory on the other distant node.
            success_prob (float): probability of a successful swapping operation (default 1).
            degradation (float): degradation factor of memory fidelity after swapping (default 0.95).
        """
        super().__init__(owner, name, left_memo, right_memo, success_prob, degradation)
    

    def start(self) -> None:
        """Method to start entanglement swapping protocol.

        Will run circuit and send measurement results to other protocols.

        Side Effects:
            Will call `update_resource_manager` method.
            Will send messages to other protocols.
        """

        log.logger.info(f"{self.owner.name} middle protocol start with ends {self.left_node}, {self.right_node}")

        assert self.left_memo.fidelity > 0 and self.right_memo.fidelity > 0
        assert self.left_memo.entangled_memory["node_id"] == self.left_node
        assert self.right_memo.entangled_memory["node_id"] == self.right_node

        if self.owner.get_generator().random() < self.success_probability():
            # swapping succeeded
            fidelity = self.updated_fidelity(self.left_memo.fidelity, self.right_memo.fidelity)
            self.is_success = True

            expire_time = min(self.left_memo.get_expire_time(), self.right_memo.get_expire_time())

            meas_samp = self.owner.get_generator().random()
            meas_res = self.owner.timeline.quantum_manager.run_circuit(
                        self.circuit, [self.left_memo.qstate_key, self.right_memo.qstate_key], meas_samp)
            meas_res = [meas_res[self.left_memo.qstate_key], meas_res[self.right_memo.qstate_key]]
            
            log.logger.info(f"{self.name} swapping succeeded, meas_res={meas_res[0]},{meas_res[1]}")
            
            msg_l = EntanglementSwappingMessage(SwappingMsgType.SWAP_RES,
                                                self.left_protocol_name, fidelity=fidelity,
                                                remote_node=self.right_memo.entangled_memory["node_id"],
                                                remote_memo=self.right_memo.entangled_memory["memo_id"],
                                                expire_time=expire_time, meas_res=[])  # empty meas_res
            msg_r = EntanglementSwappingMessage(SwappingMsgType.SWAP_RES, 
                                                self.right_protocol_name, fidelity=fidelity,
                                                remote_node=self.left_memo.entangled_memory["node_id"],
                                                remote_memo=self.left_memo.entangled_memory["memo_id"],
                                                expire_time=expire_time, meas_res=meas_res)
        else:
            # swapping failed
            log.logger.info(f"{self.name} swapping failed")
            msg_l = EntanglementSwappingMessage(SwappingMsgType.SWAP_RES,self.left_protocol_name, fidelity=0)
            msg_r = EntanglementSwappingMessage(SwappingMsgType.SWAP_RES, self.right_protocol_name, fidelity=0)

        self.owner.send_message(self.left_node, msg_l)
        self.owner.send_message(self.right_node, msg_r)

        # delay updating the memory, to update with the end node at the same time
        left_delay = self.owner.cchannels[self.left_node].delay
        future_time = round(self.owner.timeline.now() + int(left_delay))
        process = Process(self, "update_resource_manager", [self.left_memo, MemoryInfo.RAW])
        event = Event(future_time, process, self.owner.timeline.schedule_counter)
        self.owner.timeline.schedule(event)

        right_delay = self.owner.cchannels[self.right_node].delay
        future_time = round(self.owner.timeline.now() + int(right_delay))
        process = Process(self, "update_resource_manager", [self.right_memo, MemoryInfo.RAW])
        event = Event(future_time, process, self.owner.timeline.schedule_counter)
        self.owner.timeline.schedule(event)

