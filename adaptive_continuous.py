'''
Implement paper "Adaptive, Continuous Entanglement Generation for Quantum Networks" in SeQUeNCe
Paper link: https://ieeexplore.ieee.org/document/9798130
'''

from sequence.message import Message
from sequence.protocol import Protocol
from sequence.topology.node import Node
from sequence.kernel.process import Process
from sequence.kernel.event import Event
from sequence.utils import log


class AdaptiveContinuousProtocol(Protocol):
    '''This protocol continuously generates entanglement with its neighbor nodes. 
       The probability to which neighbor to entangle is computed adaptively regarding the user requests.
    '''
    def __init__(self, owner: "Node", name: str):
        super().__init__(owner, name)
    
    def loop(self) -> None:
        '''a single loop of the adaptive-continuous protocol
        '''
        # check memory
        has_memory = self.has_available_memory()

        if has_memory:
            # lock a memory
            # select neighbor, check neighbor memory
            # start entangling
            pass
        else:
            self.loop_again()


    def loop_again(self) -> None:
        '''try again later after a random delay
        '''
        random_delay = self.owner.get_generator().uniform(1e6, 2e6) # TODO caitao: make it configurable
        process = Process(self, 'loop')
        event = Event(self.owner.timeline.now() + random_delay, process)
        self.owner.timeline.schedule(event)

    def has_available_memory(self) -> bool:
        '''return True if the quantum router has avaliable memory, otherwise return False
        '''
        return False

    def received_message(self, src: str, msg: Message):
        '''override Protocol.received_message
        '''
        pass
