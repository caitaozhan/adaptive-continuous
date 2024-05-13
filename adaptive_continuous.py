'''
Implement paper "Adaptive, Continuous Entanglement Generation for Quantum Networks" in SeQUeNCe
Paper link: https://ieeexplore.ieee.org/document/9798130
'''

from sequence.protocol import Protocol

class AdaptiveContinuousProtocol(Protocol):
    '''This protocol continuously generates entanglement with its neighbor nodes. 
       The probability to which neighbor to entangle is computed adaptively regarding the user requests.
    '''
    pass
