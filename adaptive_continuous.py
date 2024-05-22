'''
Implement paper "Adaptive, Continuous Entanglement Generation for Quantum Networks" in SeQUeNCe
Paper link: https://ieeexplore.ieee.org/document/9798130
'''

from sequence.message import Message
from sequence.protocol import Protocol
from sequence.topology.node import Node


class AdaptiveContinuousProtocol(Protocol):
    '''This protocol continuously generates entanglement with its neighbor nodes. 
       The probability to which neighbor to entangle is computed adaptively regarding the user requests.
    '''
    def __init__(self, owner: "Node", name: str):
        super().__init__(owner, name)
    
    def received_message(self, src: str, msg: Message):
        '''override Protocol.received_message
        '''
        pass
