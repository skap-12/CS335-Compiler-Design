:step = 10
:dir = 1
:turn = 90
repeat 4 [
    if :dir == 1 [
        :step = :step + 5
        :dir = 0
    ] else [
        :turn = :turn * -1
        :dir = 1
    ]
    forward :step
    right :turn
]
:fstep = :step
